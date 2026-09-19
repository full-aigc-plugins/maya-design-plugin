"""Playblast + vendor-integrity tests for the Autodesk Maya Design bridge.

The bridge wraps the vendored Jimeng/Dreamina Maya uploader. Tests are
hermetic: a fake `maya.cmds` covers all snapshot/restore touchpoints, and the
Jimeng module is monkey-patched in only for the parts that matter (active
camera, run_playblast, start_local_bridge). The vendor checksum is asserted
unmodified, and the receipt is asserted to never carry `redirect_url`.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "fakes"))

from jsonschema import Draft202012Validator  # noqa: E402

import maya_bridge  # noqa: E402
from fake_maya_cmds import (  # noqa: E402
    FakeCmds,
    FakePlayblastCmds,
    MutationForbiddenError,
    install_playblast_fake,
    uninstall_fake,
)

ARTIFACT_SCHEMA = json.loads(
    (ROOT / "schemas" / "artifact_receipt.schema.json").read_text(encoding="utf-8")
)


def _artifact_validator() -> Draft202012Validator:
    return Draft202012Validator(ARTIFACT_SCHEMA)


def _populate(fake: FakePlayblastCmds) -> None:
    fake.cameras = ("camera1", "camera2")
    fake.playback_range = (1, 240)
    fake.current_time = 12
    fake.resolution = (1920, 1080)
    fake.model_panels = ("modelPanel1",)
    fake.display_modes = {"modelPanel1": "smoothShaded"}
    fake.display_textures = {"modelPanel1": True}
    fake.display_appearance = {"modelPanel1": "smoothShaded"}
    fake.materials = ()
    fake.references = ()
    fake.namespaces = ()
    fake.callbacks = ()
    fake.unknown_plugins = ()
    fake.active_camera = "camera1"
    fake.active_panel = "modelPanel1"
    fake.selection = ("pCube1",)
    fake.image_format = "png"
    fake.renderer = "vp2"


# ---------------------------------------------------------------------------
# Vendor-integrity tests
# ---------------------------------------------------------------------------


class VendorIntegrityTests(unittest.TestCase):
    def test_vendor_directory_present(self) -> None:
        self.assertTrue(maya_bridge.JIMENG_VENDOR_DIR.is_dir())

    def test_vendor_checksum_matches(self) -> None:
        # If a developer edits scripts/jimeng_third_party/, this raises.
        try:
            maya_bridge.verify_vendor_checksum()
        except maya_bridge.RestoreUnconfirmedError as exc:
            self.fail(f"Jimeng vendor was modified: {exc}")

    def test_vendor_contains_expected_modules(self) -> None:
        for name in ("__init__.py", "playblast.py", "upload_bridge.py", "dcc_config.py", "ui.py"):
            self.assertTrue(
                (maya_bridge.JIMENG_VENDOR_DIR / name).is_file(),
                f"missing vendored module: {name}",
            )


# ---------------------------------------------------------------------------
# restored_maya_state — pre/post equality under every terminal outcome
# ---------------------------------------------------------------------------


class RestoredStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_playblast_fake()
        _populate(self.fake)

    def tearDown(self) -> None:
        uninstall_fake()

    def _snapshot(self) -> dict:
        return self.fake.snapshot()

    def test_success_path_preserves_state(self) -> None:
        before = self._snapshot()
        with maya_bridge.restored_maya_state(self.fake) as snap:
            # Mutations go through cmds so the bridge can observe + restore them.
            self.fake.currentTime(99, edit=True)
            self.fake.playbackOptions(edit=True, minTime=10, maxTime=50)
            self.fake.modelPanel("modelPanel1", edit=True, camera="camera2")
            self.fake.modelPanel("modelPanel1", edit=True, displayAppearance="wireframe")
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(snap["current_time"], before["current_time"])

    def test_exception_path_still_restores(self) -> None:
        before = self._snapshot()
        with self.assertRaises(RuntimeError):
            with maya_bridge.restored_maya_state(self.fake):
                self.fake.currentTime(99, edit=True)
                raise RuntimeError("boom")
        self.assertEqual(self._snapshot(), before)

    def test_cancellation_path_still_restores(self) -> None:
        before = self._snapshot()
        with self.assertRaises(KeyboardInterrupt):
            with maya_bridge.restored_maya_state(self.fake):
                self.fake.currentTime(77, edit=True)
                raise KeyboardInterrupt()
        self.assertEqual(self._snapshot(), before)


# ---------------------------------------------------------------------------
# export_playblast — success / failure injection / receipt hygiene
# ---------------------------------------------------------------------------


class _JimengStub:
    """Stand-in for the vendored Jimeng modules loaded by the bridge."""

    def __init__(self, fake: FakePlayblastCmds, video_path: Path) -> None:
        self.fake = fake
        self.video_path = video_path
        self.bridge_result = {
            "status": "ready",
            "port": 38123,
            "redirect_url": "https://jimeng.jianying.com/ai-tool/home?channel=maya&thirdparty_id=SECRET",
            "resource_info_url": "http://127.0.0.1:38123/resouce_info?token=SECRET",
            "video": str(video_path),
        }
        self.bridge_calls = []

    def active_camera(self):  # noqa: D401
        return self.fake.active_camera

    def run_playblast(self, **kwargs):  # noqa: D401
        if self.fake.injected_failure == "playblast":
            raise RuntimeError("injected playblast failure")
        self.video_path.parent.mkdir(parents=True, exist_ok=True)
        self.video_path.write_bytes(b"fake-mp4-bytes")
        return str(self.video_path)

    def start_local_bridge(self, **kwargs):  # noqa: D401
        self.bridge_calls.append(dict(kwargs))
        if self.fake.injected_failure == "bridge":
            raise RuntimeError("injected bridge failure")
        return dict(self.bridge_result)


def _install_jimeng_stub(fake: FakePlayblastCmds, video_path: Path) -> _JimengStub:
    """Patch the lazy import helpers to return a stub Jimeng module."""

    stub = _JimengStub(fake, video_path)
    pb_module = sys.modules.setdefault(
        "_jimeng_pb_stub",
        sys.modules[__name__],
    )
    ub_module = sys.modules.setdefault(
        "_jimeng_ub_stub",
        sys.modules[__name__],
    )
    pb_module.active_camera = stub.active_camera  # type: ignore[attr-defined]
    pb_module.run_playblast = stub.run_playblast  # type: ignore[attr-defined]
    ub_module.start_local_bridge = stub.start_local_bridge  # type: ignore[attr-defined]
    maya_bridge._import_jimeng_playblast = lambda: pb_module  # type: ignore[assignment]
    maya_bridge._import_jimeng_upload_bridge = lambda: ub_module  # type: ignore[assignment]
    sys.modules.pop("_maya_design_bridge_sessions", None)
    return stub


def _base_request(scene_id: str, **overrides) -> dict:
    base = {
        "mode": "white_model",
        "camera": "camera1",
        "start_frame": 1,
        "end_frame": 30,
        "width": 1920,
        "height": 1080,
        "frame_rate": 24,
        "scene_id": scene_id,
    }
    base.update(overrides)
    return base


class ExportPlayblastTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_playblast_fake()
        _populate(self.fake)
        self.tmpdir = ROOT / "tests" / "tmp_playblast"
        self.tmpdir.mkdir(exist_ok=True)
        self.video_path = self.tmpdir / "fake.mp4"
        self.stub = _install_jimeng_stub(self.fake, self.video_path)

    def tearDown(self) -> None:
        uninstall_fake()
        maya_bridge.consume_bridge_session_log()
        sys.modules.pop("_jimeng_pb_stub", None)
        sys.modules.pop("_jimeng_ub_stub", None)
        if self.video_path.exists():
            self.video_path.unlink()

    def test_white_model_produces_valid_receipt(self) -> None:
        before = self.fake.snapshot()
        receipt = maya_bridge.export_playblast(self.fake, _base_request("11111111-1111-4111-8111-111111111111"))
        self.fake.snapshot()  # ensure post-call access works

        errors = sorted(_artifact_validator().iter_errors(receipt), key=lambda e: str(e.path))
        self.assertEqual(errors, [], f"receipt invalid: {[e.message for e in errors]}")
        self.assertEqual(receipt["display_mode"], "white_model")
        self.assertEqual(receipt["restoration_status"], "restored")
        self.assertEqual(receipt["plugin_id"], "maya-design")
        self.assertNotIn("redirect_url", receipt)
        self.assertNotIn("resource_info_url", receipt)

    def test_material_preview_mode_is_accepted(self) -> None:
        receipt = maya_bridge.export_playblast(
            self.fake, _base_request("11111111-1111-4111-8111-111111111111", mode="material_preview")
        )
        self.assertEqual(receipt["display_mode"], "material_preview")

    def test_existing_video_mode_does_not_mutate_state(self) -> None:
        # Drop in a real local video file for existing-video mode.
        local = self.tmpdir / "local.mp4"
        local.write_bytes(b"local-mp4")
        before = self.fake.snapshot()
        receipt = maya_bridge.export_playblast(
            self.fake,
            _base_request(
                "11111111-1111-4111-8111-111111111111",
                mode="existing_video",
                video_path=str(local),
            ),
        )
        after = self.fake.snapshot()
        self.assertEqual(receipt["display_mode"], "existing_video")
        self.assertEqual(receipt["restoration_status"], "restored")
        self.assertEqual(before, after, "existing-video mode must not mutate scene state")
        local.unlink()

    def test_failure_at_playblast_is_reported(self) -> None:
        self.fake.inject_failure("playblast")
        with self.assertRaises(maya_bridge.PlayblastFailedError):
            maya_bridge.export_playblast(
                self.fake, _base_request("11111111-1111-4111-8111-111111111111")
            )

    def test_failure_at_bridge_is_reported(self) -> None:
        self.fake.inject_failure("bridge")
        with self.assertRaises(maya_bridge.PlayblastFailedError):
            maya_bridge.export_playblast(
                self.fake, _base_request("11111111-1111-4111-8111-111111111111")
            )

    def test_redirect_url_is_captured_separately_not_in_receipt(self) -> None:
        receipt = maya_bridge.export_playblast(
            self.fake, _base_request("11111111-1111-4111-8111-111111111111")
        )
        self.assertNotIn("redirect_url", receipt)
        log = maya_bridge.consume_bridge_session_log()
        self.assertEqual(len(log), 1)
        self.assertIn("redirect_url", log[0])
        self.assertIn("SECRET", log[0]["redirect_url"])

    def test_camera_not_found_raises(self) -> None:
        with self.assertRaises(maya_bridge.CameraNotFoundError):
            maya_bridge.export_playblast(
                self.fake,
                _base_request(
                    "11111111-1111-4111-8111-111111111111",
                    camera="does_not_exist",
                ),
            )

    def test_camera_flow_returns_link_separately_from_artifact_receipt(self) -> None:
        result = maya_bridge.run_jimeng_flow(
            self.fake,
            _base_request(
                "11111111-1111-4111-8111-111111111111",
                authorize_upload=True,
            ),
        )

        self.assertEqual(result["artifact_receipt"]["display_mode"], "white_model")
        self.assertNotIn("redirect_url", result["artifact_receipt"])
        self.assertEqual(result["jimeng_link"]["status"], "ready")
        self.assertIn("channel=maya", result["jimeng_link"]["redirect_url"])

    def test_existing_video_flow_calls_official_bridge_and_returns_link(self) -> None:
        local = self.tmpdir / "existing.mp4"
        local.write_bytes(b"existing-video")
        self.stub.bridge_result["video"] = str(local)
        try:
            result = maya_bridge.run_jimeng_flow(
                self.fake,
                _base_request(
                    "11111111-1111-4111-8111-111111111111",
                    mode="existing_video",
                    video_path=str(local),
                    authorize_upload=True,
                    prompt="产品动画",
                ),
            )
        finally:
            local.unlink()

        self.assertEqual(len(self.stub.bridge_calls), 1)
        self.assertEqual(self.stub.bridge_calls[0]["video_path"], str(local))
        self.assertEqual(self.stub.bridge_calls[0]["prompt"], "产品动画")
        self.assertEqual(result["jimeng_link"]["status"], "ready")
        self.assertEqual(result["artifact_receipt"]["display_mode"], "existing_video")

    def test_existing_video_artifact_tracks_the_file_served_by_official_bridge(self) -> None:
        source = self.tmpdir / "source.mov"
        source.write_bytes(b"source-video")
        self.video_path.write_bytes(b"converted-mp4")
        try:
            result = maya_bridge.run_jimeng_flow(
                self.fake,
                _base_request(
                    "11111111-1111-4111-8111-111111111111",
                    mode="existing_video",
                    video_path=str(source),
                    authorize_upload=True,
                ),
            )
        finally:
            source.unlink()

        artifact = result["artifact_receipt"]
        self.assertEqual(artifact["media_path"], str(self.video_path))
        self.assertEqual(artifact["media_sha256"], maya_bridge._sha256_file(self.video_path))

    def test_link_flow_requires_explicit_upload_authorization(self) -> None:
        with self.assertRaises(maya_bridge.UploadNotAuthorizedError):
            maya_bridge.run_jimeng_flow(
                self.fake,
                _base_request("11111111-1111-4111-8111-111111111111"),
            )
        self.assertEqual(self.stub.bridge_calls, [])


class ExistingVideoReceiptTests(unittest.TestCase):
    def test_existing_video_receipt_has_required_fields(self) -> None:
        tmp = ROOT / "tests" / "tmp_existing.mp4"
        tmp.write_bytes(b"x" * 4096)
        try:
            request = {
                "mode": "existing_video",
                "video_path": str(tmp),
                "scene_id": "11111111-1111-4111-8111-111111111111",
                "duration_seconds": 5.0,
                "frame_rate": 24.0,
                "width": 1280,
                "height": 720,
            }
            receipt = maya_bridge.export_playblast(None, request)  # type: ignore[arg-type]
            errors = sorted(_artifact_validator().iter_errors(receipt), key=lambda e: str(e.path))
            self.assertEqual(errors, [])
            self.assertEqual(receipt["display_mode"], "existing_video")
            self.assertEqual(receipt["restoration_status"], "restored")
            self.assertEqual(len(receipt["media_sha256"]), 64)
        finally:
            tmp.unlink()


if __name__ == "__main__":
    unittest.main()
