"""Tests for the preflight checker and the runtime-matrix runner.

Neither script installs or licenses Maya. The preflight is tested on both
outcomes with the same stub-`mayapy` technique the other runner tests use; the
matrix runner is tested for its failure paths and its markdown rendering, since
its success path is defined to require a real Maya installation.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import maya_preflight  # noqa: E402
import run_runtime_matrix  # noqa: E402


def _write_stub_maya(root: Path, *, version: str = "2026") -> Path:
    macos = root / "Maya.app" / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    body = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import json, sys
        if len(sys.argv) >= 3 and sys.argv[1] == '-c':
            cmd = sys.argv[2]
            if 'sys.version_info' in cmd:
                print('3.7'); sys.exit(0)
            if 'sys.path' in cmd:
                print(json.dumps(['{macos}', '/opt/maya/modules'])); sys.exit(0)
        sys.exit(2)
        """
    )
    shim = macos / "mayapy"
    shim.write_text(body, encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    (macos / "version").write_text(version, encoding="utf-8")
    return shim


class PreflightTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "maya_preflight.py"), *args],
            capture_output=True, text=True,
        )

    def test_reports_usable_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _write_stub_maya(Path(tmp))
            result = self._run("--explicit-root", tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Maya is usable", result.stdout)
            self.assertIn("2026", result.stdout)

    def test_reports_not_usable_with_guidance_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--explicit-root", tmp)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Maya is NOT usable", result.stdout)

    def test_guidance_names_the_official_trial_and_refuses_to_auto_install(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--explicit-root", tmp)
            flat = result.stdout.replace("\n", " ")
            # The user has to fetch it themselves; the tool must say so and
            # point at the official route rather than any mirror.
            self.assertIn("autodesk.com", flat)
            self.assertIn("autodesk.com/products/maya/free-trial", flat)
            self.assertIn("installs, downloads, or licenses Maya for you", flat)
            # And it must not recommend a third-party/pirate mirror.
            for mirror in ("macsc", "pcbeta", "crack", "破解", "torrent"):
                self.assertNotIn(mirror, flat.lower())

    def test_json_mode_is_parseable_on_both_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = self._run("--explicit-root", tmp, "--json")
            self.assertEqual(json.loads(missing.stdout)["usable"], False)

            _write_stub_maya(Path(tmp))
            present = self._run("--explicit-root", tmp, "--json")
            payload = json.loads(present.stdout)
            self.assertEqual(payload["usable"], True)
            self.assertEqual(payload["version"], "2026")


class MacOSRangeTests(unittest.TestCase):
    """Autodesk documents 13.x-15.x for Maya 2026; newer is flagged, not hidden."""

    def test_flags_a_macos_above_the_documented_range(self) -> None:
        original = maya_preflight._macos_version
        maya_preflight._macos_version = lambda: (26, 6, 2)
        try:
            info = maya_preflight._report_environment()
        finally:
            maya_preflight._macos_version = original
        self.assertIn("macos_outside_documented_range", info)
        self.assertIn("13", info["macos_outside_documented_range"])

    def test_does_not_flag_a_documented_version(self) -> None:
        original = maya_preflight._macos_version
        maya_preflight._macos_version = lambda: (14, 5, 0)
        try:
            info = maya_preflight._report_environment()
        finally:
            maya_preflight._macos_version = original
        self.assertNotIn("macos_outside_documented_range", info)


class NoInstallGuaranteeTests(unittest.TestCase):
    def test_preflight_never_installs_or_downloads(self) -> None:
        source = (SCRIPTS / "maya_preflight.py").read_text(encoding="utf-8")
        for forbidden in ("pip.main", "ensurepip", "urlretrieve", "curl", "brew install"):
            self.assertNotIn(forbidden, source)

    def test_matrix_never_installs_or_downloads(self) -> None:
        source = (SCRIPTS / "run_runtime_matrix.py").read_text(encoding="utf-8")
        for forbidden in ("pip.main", "ensurepip", "urlretrieve", "brew install"):
            self.assertNotIn(forbidden, source)


class MatrixRunnerTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "run_runtime_matrix.py"), *args],
            capture_output=True, text=True,
        )

    def test_without_maya_it_fails_cleanly_and_points_at_the_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--scene", "scenes/hero.ma",
                               "--explicit-root", str(Path(tmp) / "absent"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("no usable Maya", result.stderr)
            self.assertIn("maya_preflight.py", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_markdown_rendering_covers_every_gate_row(self) -> None:
        evidence = {
            "generated_at": "2026-09-14T00:00:00Z",
            "environment": {"os": "macOS-26.6.2-arm64", "machine": "arm64",
                            "host_python": "3.13.0"},
            "steps": {
                "probe": {"status": "observed", "mayapy": "/x/mayapy",
                          "maya_version": "2026", "python_version": "3.7",
                          "module_path_count": 12},
                "inspect": {"status": "observed", "approved_camera": "perspShape",
                            "resolution": {"width": 1920, "height": 1080},
                            "display_mode": "material_preview",
                            "inspection_status": "ok", "scene_id": "abc",
                            "deterministic": True},
                "export": {"status": "observed", "mode": "white_model",
                           "dimensions": {"width": 1280, "height": 720},
                           "codec": "avc1", "duration_seconds": 2.0,
                           "file_size_bytes": 4096},
                "restore": {"status": "observed", "camera_unchanged": True,
                            "frame_range_unchanged": True,
                            "resolution_unchanged": True, "scene_id_unchanged": True},
                "bridge": {"status": "not_authorized", "note": "re-run with --authorize-upload"},
                "handoff": {"status": "observed", "validator": "handoff_validator.py",
                            "errors": []},
            },
        }
        markdown = run_runtime_matrix.render_markdown(evidence)
        for expected in ("Probe", "Inspect", "Playblast", "Restoration", "Bridge", "Handoff"):
            self.assertIn(expected, markdown, f"missing gate row: {expected}")
        self.assertIn("Maya 2026", markdown)
        self.assertIn("Python 3.7", markdown)

    def test_markdown_does_not_leak_a_bridge_token(self) -> None:
        # redirect_url carries a live token; the runner must never record it.
        source = (SCRIPTS / "run_runtime_matrix.py").read_text(encoding="utf-8")
        self.assertIn("Deliberately not recording redirect_url", source)
        self.assertNotIn('"redirect_url": link', source)


if __name__ == "__main__":
    unittest.main()
