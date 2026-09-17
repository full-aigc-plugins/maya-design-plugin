"""Hermetic tests for the Maya runtime probe.

We never invoke a real Maya install. Each test creates a tiny `mayapy` shim
script and points the probe at it via filesystem fixtures.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import maya_runner  # noqa: E402  - intentional after sys.path injection

PLUGIN_ID = "maya-design"


def _write_executable(target: Path, body: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(body), encoding="utf-8")
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return target


def _make_macos_shim(root: Path, *, version: str, python_version: str) -> Path:
    macos = root / "Maya.app" / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    body = f"""\
        #!/usr/bin/env python3
        import json, sys
        if sys.argv[1] == '-c':
            cmd = sys.argv[2]
            if 'sys.version_info' in cmd:
                print('{python_version}')
                raise SystemExit(0)
            if 'sys.path' in cmd:
                print(json.dumps(['{macos}', '/opt/maya/modules']))
                raise SystemExit(0)
        print('unexpected argv', sys.argv)
        raise SystemExit(2)
    """
    shim = _write_executable(macos / "mayapy", body)
    # Drop a version file alongside the binary so the probe can read the Maya year.
    (macos / "version").write_text(version, encoding="utf-8")
    return shim


def _make_windows_shim(root: Path, *, version: str, python_version: str) -> Path:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    body = f"""\
        #!/usr/bin/env python3
        import json, sys
        if sys.argv[1] == '-c':
            cmd = sys.argv[2]
            if 'sys.version_info' in cmd:
                print('{python_version}')
                raise SystemExit(0)
            if 'sys.path' in cmd:
                print(json.dumps(['{bin_dir}', r'C:\\Maya\\modules']))
                raise SystemExit(0)
        print('unexpected argv', sys.argv)
        raise SystemExit(2)
    """
    shim = _write_executable(bin_dir / "mayapy.exe", body)
    (bin_dir / "version").write_text(version, encoding="utf-8")
    # Windows layout — maya.exe should also be present so we can verify it is exposed.
    (bin_dir / "maya.exe").write_bytes(b"MZ")
    return shim


class DiscoverTests(unittest.TestCase):
    def test_macos_layout_finds_runtime(self) -> None:
        with self._temp_root() as root:
            _make_macos_shim(root, version="2024", python_version="3.7")
            runtime = maya_runner.discover_maya(str(root), "")
            self.assertEqual(runtime.python_version, "3.7")
            self.assertEqual(runtime.mayapy.parent.parent.parent.name, "Maya.app")
            self.assertEqual(runtime.version, "2024")

    def test_windows_layout_finds_runtime(self) -> None:
        with self._temp_root() as root:
            _make_windows_shim(root, version="2022", python_version="3.7")
            runtime = maya_runner.discover_maya(str(root), "")
            self.assertEqual(runtime.mayapy.name, "mayapy.exe")
            self.assertEqual(runtime.version, "2022")
            self.assertIsNotNone(runtime.maya)
            self.assertTrue(str(runtime.maya).endswith("bin/maya.exe"))

    def test_unicode_and_spaced_path(self) -> None:
        with self._temp_root(prefix="中文 目录 ") as root:
            _make_macos_shim(root, version="2024", python_version="3.7")
            runtime = maya_runner.discover_maya(str(root), "")
            self.assertTrue(runtime.mayapy.exists())

    def test_missing_mayapy_raises_not_found(self) -> None:
        with self._temp_root() as root:
            with self.assertRaises(maya_runner.MayaNotFoundError) as ctx:
                maya_runner.discover_maya(str(root), "")
            self.assertEqual(ctx.exception.code, "MAYA_NOT_FOUND")

    def test_unsupported_python_raises_abi_mismatch(self) -> None:
        with self._temp_root() as root:
            _make_macos_shim(root, version="2024", python_version="3.11")
            with self.assertRaises(maya_runner.MayaAbiMismatchError) as ctx:
                maya_runner.discover_maya(str(root), "")
            self.assertEqual(ctx.exception.code, "ABI_MISMATCH")

    def test_module_path_load_failure_raises_module_load_error(self) -> None:
        with self._temp_root() as root:
            macos = root / "Maya.app" / "Contents" / "MacOS"
            macos.mkdir(parents=True, exist_ok=True)
            body = textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import sys
                if 'sys.path' in sys.argv[2]:
                    raise SystemExit(7)
                print('3.7')
                """
            )
            _write_executable(macos / "mayapy", body)
            with self.assertRaises(maya_runner.MayaModuleLoadError) as ctx:
                maya_runner.discover_maya(str(root), "")
            self.assertEqual(ctx.exception.code, "MODULE_LOAD_FAILED")

    def test_search_path_supports_multiple_roots(self) -> None:
        with self._temp_root() as a, self._temp_root() as b:
            _make_macos_shim(b, version="2024", python_version="3.7")
            runtime = maya_runner.discover_maya(None, f"{a}{os.pathsep}{b}")
            self.assertEqual(runtime.version, "2024")

    # --- helpers ------------------------------------------------------------

    @staticmethod
    def _temp_root(prefix: str = "maya-root-") -> "_TempDir":
        return _TempDir(prefix)


class _TempDir:
    def __init__(self, prefix: str) -> None:
        import tempfile

        self.path = Path(tempfile.mkdtemp(prefix=prefix))

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *_exc: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


class ArgvBuilderTests(unittest.TestCase):
    def test_build_batch_argv_uses_argv_only(self) -> None:
        runtime = maya_runner.MayaRuntime(
            maya=None,
            mayapy=Path("/opt/maya/bin/mayapy"),
            version="2024",
            python_version="3.7",
            module_paths=(),
        )
        argv = maya_runner.build_batch_argv(runtime, Path("/tmp/request.json"))
        self.assertIsInstance(argv, list)
        # mayapy <runner> <request.json> <response.json>: four discrete
        # elements so paths never need quoting or escaping.
        self.assertEqual(argv[0], "/opt/maya/bin/mayapy")
        self.assertEqual(argv[1], str(maya_runner.RUNNER_SCRIPT))
        self.assertEqual(argv[2], "/tmp/request.json")
        self.assertTrue(argv[3].endswith("response.json"))
        self.assertEqual(len(argv), 4)


class SubprocessHardeningTests(unittest.TestCase):
    """Prove the subprocess layer is argv-only, shell-less, allowlisted, time-bounded."""

    def test_subprocess_called_without_shell_and_with_filtered_env(self) -> None:
        captured: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(argv, **kwargs):  # type: ignore[no-untyped-def]
            captured.append((list(argv), dict(kwargs)))
            argv_list = list(argv)
            fake_stdout = (
                '[".", "/opt/maya/modules"]'
                if any("sys.path" in str(a) for a in argv_list)
                else "3.7"
            )

            class _Result:
                returncode = 0
                stdout = fake_stdout
                stderr = ""

            return _Result()

        with _TempDir("maya-probe-") as root:
            _make_macos_shim(root, version="2024", python_version="3.7")
            # Monkey-patch subprocess.run for the duration of this test only.
            original = maya_runner.subprocess.run
            maya_runner.subprocess.run = fake_run  # type: ignore[assignment]
            try:
                maya_runner.discover_maya(
                    str(root),
                    "",
                    env={"PATH": "/opt/maya/bin", "SECRET": "should-be-filtered"},
                    timeout=12.5,
                )
            finally:
                maya_runner.subprocess.run = original  # type: ignore[assignment]

        self.assertTrue(captured, "expected subprocess.run to be invoked")
        argv, kwargs = captured[0]
        self.assertEqual(kwargs.get("shell"), False)
        self.assertIsInstance(argv, list)
        env = kwargs.get("env") or {}
        self.assertNotIn("SECRET", env)
        self.assertIn("PATH", env)
        self.assertEqual(kwargs.get("timeout"), 12.5)


class EnvironmentAllowlistTests(unittest.TestCase):
    def test_filter_drops_disallowed_vars(self) -> None:
        base = {"PATH": "/bin", "AWS_SECRET": "leak", "GITHUB_TOKEN": "leak", "TMPDIR": "/tmp"}
        filtered = maya_runner._filter_environment(base)
        self.assertEqual(set(filtered), {"PATH", "TMPDIR"})

    def test_filter_preserves_required_vars(self) -> None:
        base = {"PATH": "/bin", "MAYA_LOCATION": "/opt/maya", "PYTHONPATH": "/opt/maya/modules"}
        filtered = maya_runner._filter_environment(base)
        for key in ("PATH", "MAYA_LOCATION", "PYTHONPATH"):
            self.assertIn(key, filtered)


class NoInstallerGuaranteeTests(unittest.TestCase):
    def test_module_does_not_import_pip_or_subprocess_installers(self) -> None:
        # Reading the source is enough — we never install anything at runtime.
        source = (ROOT / "scripts" / "maya_runner.py").read_text(encoding="utf-8")
        for forbidden in ("pip.main", "subprocess.check_call", "ensurepip"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
