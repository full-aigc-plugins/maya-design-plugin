"""codex-maya -> codex-dreamina-3d handoff compatibility.

The plan's Task 7 requires: "Confirm output receipt compatibility against the
same fixtures used by `codex-dreamina-3d`."

`codex-dreamina-3d` does not consume `codex-maya`'s own artifact receipt. It
discovers companions with `scripts/capability_probe.py` and validates an
incoming preview receipt with `scripts/handoff_validator.py`. Before this
module existed, `codex-maya` had neither `receipt_contract_versions` in its
manifest nor a `bin/maya_adapter`, so `discover_companions` returned `[]` and
the handoff could not start at all.

These tests run the sibling's **real** code -- imported from
`../codex-dreamina-3d-plugin/scripts/` -- rather than a re-implementation. A
re-implementation would only prove that two copies of my own assumptions agree.
Where the sibling repository is not checked out, the cross-repo tests skip with
an explicit reason so the gap is visible rather than silently green.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dreamina_adapter  # noqa: E402
import media_probe  # noqa: E402

# Reuse the hand-built minimal MP4 the media-probe tests already maintain.
sys.path.insert(0, str(ROOT / "tests"))
from test_media_probe import _build_minimal_mp4  # noqa: E402

THREE_D = ROOT.parent / "codex-dreamina-3d-plugin"
THREE_D_SCRIPTS = THREE_D / "scripts"

CONTRACT_KEYS = {
    "schema_version", "producer_plugin", "producer_version", "artifact_id",
    "path", "sha256", "codec", "container", "dimensions", "fps",
    "duration_seconds", "bytes", "camera", "frame_range", "preview_mode",
    "restoration",
}


def _load_three_d(module_name: str):
    """Import a module from the sibling plugin, or None when it is absent."""

    if not (THREE_D_SCRIPTS / f"{module_name}.py").is_file():
        return None
    if str(THREE_D_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(THREE_D_SCRIPTS))
    return __import__(module_name)


class _HandoffCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="maya-handoff-"))
        self.media = self.tmp / "playblast.mp4"
        # 1280x720 @ 24fps, 2.0s -- inside every consumer range.
        self.media.write_bytes(_build_minimal_mp4(width=1280, height=720, fps=24, duration_seconds=2.0))

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _receipt(self, *, preview_mode: str = "camera_render", fps: float = 24.0) -> dict:
        media = media_probe.probe(self.media)
        return dreamina_adapter.build_preview_receipt(
            artifact_id="maya-artifact-1",
            media_path=self.media,
            media=media,
            sha256=media_probe.sha256(self.media),
            fps=fps,
            camera_name="perspShape",
            frame_range={"start": 1, "end": 90},
            preview_mode=preview_mode,
        )


class ReceiptShapeTests(_HandoffCase):
    """Self-contained assertions on the consumer's documented shape."""

    def test_exact_key_set(self) -> None:
        self.assertEqual(set(self._receipt()), CONTRACT_KEYS)

    def test_identity_and_constants(self) -> None:
        receipt = self._receipt()
        self.assertEqual(receipt["schema_version"], "1.0.0")
        self.assertEqual(receipt["producer_plugin"], "codex-maya")
        self.assertEqual(receipt["producer_version"], "0.1.0")
        self.assertEqual(receipt["codec"], "h264")
        self.assertEqual(receipt["container"], "mp4")

    def test_dimensions_are_nested_integers(self) -> None:
        dims = self._receipt()["dimensions"]
        self.assertEqual(dims, {"width": 1280, "height": 720})
        self.assertIsInstance(dims["width"], int)
        self.assertIsInstance(dims["height"], int)

    def test_sha256_is_64_lowercase_hex_and_matches_disk(self) -> None:
        receipt = self._receipt()
        self.assertEqual(len(receipt["sha256"]), 64)
        self.assertEqual(receipt["sha256"], media_probe.sha256(self.media))

    def test_bytes_match_disk(self) -> None:
        self.assertEqual(self._receipt()["bytes"], self.media.stat().st_size)

    def test_restoration_status_is_confirmed_not_restored(self) -> None:
        # codex-maya's internal receipt says "restored"; the consumer requires
        # the literal "confirmed". The adapter is the translation point.
        self.assertEqual(self._receipt()["restoration"]["status"], "confirmed")

    def test_camera_is_an_object_with_a_name(self) -> None:
        self.assertEqual(self._receipt()["camera"], {"name": "perspShape"})

    def test_frame_range_is_ints_with_start_le_end(self) -> None:
        frame_range = self._receipt()["frame_range"]
        self.assertEqual(frame_range, {"start": 1, "end": 90})

    def test_preview_mode_maps_from_display_mode(self) -> None:
        self.assertEqual(
            dreamina_adapter._DISPLAY_TO_PREVIEW,
            {"white_model": "camera_render", "material_preview": "camera_render",
             "existing_video": "local_video"},
        )


class RefusesOutOfRangeTests(_HandoffCase):
    """The adapter must refuse rather than emit a receipt the consumer rejects."""

    def _build(self, **overrides):
        media = media_probe.probe(self.media)
        media.update(overrides.pop("media", {}))
        kwargs = dict(
            artifact_id="a", media_path=self.media, media=media,
            sha256=media_probe.sha256(self.media), fps=24.0,
            camera_name="perspShape", frame_range={"start": 1, "end": 90},
            preview_mode="camera_render",
        )
        kwargs.update(overrides)
        return dreamina_adapter.build_preview_receipt(**kwargs)

    def test_rejects_non_h264_codec(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(media={"codec": "hevc"})

    def test_rejects_width_above_consumer_max(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError) as ctx:
            self._build(media={"width": 8192})
        self.assertIn("outside", str(ctx.exception))

    def test_rejects_width_below_consumer_min(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(media={"width": 8})

    def test_rejects_zero_duration(self) -> None:
        # A zero-duration receipt is rejected by the consumer's (0, 60] range.
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(media={"duration_seconds": 0.0})

    def test_rejects_duration_over_60s(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(media={"duration_seconds": 61.0})

    def test_rejects_fps_out_of_range(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(fps=300.0)
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(fps=0.0)

    def test_rejects_unknown_preview_mode(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(preview_mode="wireframe")

    def test_rejects_inverted_frame_range(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(frame_range={"start": 90, "end": 1})

    def test_rejects_empty_camera_name(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(camera_name="")

    def test_rejects_bad_sha256(self) -> None:
        with self.assertRaises(dreamina_adapter.AdapterError):
            self._build(sha256="nothex")


class CrossRepoSibling(unittest.TestCase):
    """Skip helper that keeps an absent sibling visible instead of silently green."""

    @classmethod
    def setUpClass(cls) -> None:
        if not THREE_D_SCRIPTS.is_dir():
            raise unittest.SkipTest(
                f"codex-dreamina-3d-plugin not checked out at {THREE_D}; "
                "cross-repo handoff assertions did not run"
            )


class RealValidatorTests(_HandoffCase, CrossRepoSibling):
    """Run codex-dreamina-3d's own validator against a receipt we produced."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.validator = _load_three_d("handoff_validator")
        if cls.validator is None:
            raise unittest.SkipTest("handoff_validator.py not importable")

    def test_real_validator_accepts_a_camera_render_receipt(self) -> None:
        errors = self.validator.validate_artifact(self._receipt(), self.media)
        self.assertEqual(errors, [], f"consumer rejected the receipt: {errors}")

    def test_real_validator_accepts_a_local_video_receipt(self) -> None:
        receipt = self._receipt(preview_mode="local_video")
        errors = self.validator.validate_artifact(receipt, self.media)
        self.assertEqual(errors, [], f"consumer rejected the receipt: {errors}")

    def test_real_validator_still_rejects_a_tampered_receipt(self) -> None:
        # Proves the acceptance above is not vacuous: the same validator must
        # reject a receipt whose declared size no longer matches the file.
        receipt = self._receipt()
        receipt["bytes"] = receipt["bytes"] + 1
        errors = self.validator.validate_artifact(receipt, self.media)
        self.assertTrue(any("bytes" in e for e in errors), errors)


class RealCapabilityProbeTests(_HandoffCase, CrossRepoSibling):
    """Run codex-dreamina-3d's own discovery against this checkout."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.probe = _load_three_d("capability_probe")
        if cls.probe is None:
            raise unittest.SkipTest("capability_probe.py not importable")

    def test_companion_is_discoverable_from_a_marketplace_style_root(self) -> None:
        # The probe expects <root>/<plugin_id>/.codex-plugin/plugin.json and an
        # executable at bin/maya_adapter.
        root = self.tmp / "root"
        root.mkdir()
        (root / "codex-maya").symlink_to(ROOT)

        companions = self.probe.discover_companions([root])
        maya = [c for c in companions if c.plugin_id == "codex-maya"]
        self.assertEqual(len(maya), 1, f"codex-maya not discovered: {companions}")
        companion = maya[0]
        self.assertTrue(companion.is_callable, "adapter is not executable")
        self.assertEqual(companion.version, "0.1.0")
        self.assertIn("1.0.0", companion.contract_versions)

    def test_manifest_advertises_the_supported_contract_version(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("1.0.0", manifest.get("receipt_contract_versions", []))


class AdapterExecutableTests(unittest.TestCase):
    """`bin/maya_adapter` is the executable the consumer's probe looks for."""

    def setUp(self) -> None:
        self.adapter = ROOT / "bin" / "maya_adapter"

    def test_exists_and_is_executable(self) -> None:
        self.assertTrue(self.adapter.is_file(), "missing bin/maya_adapter")
        mode = self.adapter.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "bin/maya_adapter is not executable")

    def test_matches_the_blenders_adapter_shape(self) -> None:
        # Both adapters are thin wrappers that put scripts/ on sys.path and call
        # their module's main().
        text = self.adapter.read_text(encoding="utf-8")
        self.assertIn("from dreamina_adapter import main", text)
        self.assertIn("sys.path", text)

    def test_status_mode_writes_unknown_when_no_receipt_exists(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "nested" / "receipt.json"
            result = subprocess.run(
                [sys.executable, str(self.adapter), "--receipt", str(receipt), "--status"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(receipt.read_text())["status"], "unknown")

    def test_status_mode_returns_zero_when_a_receipt_exists(self) -> None:
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "receipt.json"
            receipt.write_text("{}")
            result = subprocess.run(
                [sys.executable, str(self.adapter), "--receipt", str(receipt), "--status"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_failure_is_written_to_the_receipt_file_not_only_stderr(self) -> None:
        # The consumer reads the receipt file; a bare stderr traceback would
        # leave it with nothing to classify.
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "receipt.json"
            result = subprocess.run(
                [sys.executable, str(self.adapter),
                 "--request", str(Path(tmp) / "absent.json"),
                 "--receipt", str(receipt)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(receipt.read_text())
            self.assertEqual(payload["status"], "failed")
            self.assertTrue(payload["error"])


if __name__ == "__main__":
    unittest.main()
