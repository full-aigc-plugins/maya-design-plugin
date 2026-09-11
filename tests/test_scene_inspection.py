"""Hermetic scene inspection tests against the fake `maya.cmds`."""

from __future__ import annotations

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
    MutationForbiddenError,
    install_fake,
    uninstall_fake,
)


def _validator() -> Draft202012Validator:
    schema_path = ROOT / "schemas" / "scene_receipt.schema.json"
    import json

    return Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))


def _populate(fake: FakeCmds) -> None:
    fake.cameras = ("camera1", "camera2")
    fake.playback_range = (1, 240)
    fake.current_time = 12
    fake.resolution = (1920, 1080)
    fake.model_panels = ("modelPanel1",)
    fake.display_modes = {"modelPanel1": "smoothShaded"}
    fake.materials = ("lambert1",)
    fake.references = ("ref1.ma",)
    fake.namespaces = ("ns1",)
    fake.callbacks = ("frame_change",)
    fake.unknown_plugins = ()


def _scene_path() -> Path:
    return Path("scenes/hero.ma")


class InspectSceneHappyPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_fake()
        _populate(self.fake)

    def tearDown(self) -> None:
        uninstall_fake()

    def test_receipt_matches_schema(self) -> None:
        receipt = maya_bridge.inspect_scene(self.fake, _scene_path())
        errors = sorted(_validator().iter_errors(receipt), key=lambda e: str(e.path))
        self.assertEqual(errors, [], f"receipt failed schema: {[e.message for e in errors]}")

    def test_receipt_carries_locked_identity(self) -> None:
        receipt = maya_bridge.inspect_scene(self.fake, _scene_path())
        self.assertEqual(receipt["schema_version"], "1.0.0")
        self.assertEqual(receipt["plugin_id"], "codex-maya")
        self.assertEqual(receipt["approved_camera"], "camera1")

    def test_receipt_includes_all_lists(self) -> None:
        receipt = maya_bridge.inspect_scene(self.fake, _scene_path())
        self.assertEqual(receipt["materials"], ["lambert1"])
        self.assertEqual(receipt["references"], ["ref1.ma"])
        self.assertEqual(receipt["namespaces"], ["ns1"])
        self.assertEqual(receipt["callbacks"], ["frame_change"])
        self.assertEqual(receipt["unknown_plugins"], [])
        self.assertEqual(receipt["inspection_status"], "ok")


class NoMutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_fake()
        _populate(self.fake)
        self.fake.selection = ("pCube1",)
        self.fake.loaded_plugins = ("mtoa",)

    def tearDown(self) -> None:
        uninstall_fake()

    def test_selection_is_not_changed(self) -> None:
        before = tuple(self.fake.ls_sl())
        receipt = maya_bridge.inspect_scene(self.fake, _scene_path())
        after = tuple(self.fake.ls_sl())
        self.assertEqual(before, after)
        self.assertEqual(receipt["unknown_plugins"], [])

    def test_current_time_is_not_changed(self) -> None:
        before = self.fake.current_time
        maya_bridge.inspect_scene(self.fake, _scene_path())
        self.assertEqual(self.fake.current_time, before)

    def test_no_plugin_is_loaded(self) -> None:
        loaded_before = tuple(self.fake.loaded_plugins)
        maya_bridge.inspect_scene(self.fake, _scene_path())
        self.assertEqual(tuple(self.fake.loaded_plugins), loaded_before)
        # No fake call should ever reach a mutator.
        self.assertEqual(self.fake.mutating_calls(), [])

    def test_unknown_plugins_flag_status_degraded(self) -> None:
        self.fake.unknown_plugins = ("someBrokenPlugin",)
        receipt = maya_bridge.inspect_scene(self.fake, _scene_path())
        self.assertEqual(receipt["inspection_status"], "degraded")
        self.assertEqual(receipt["unknown_plugins"], ["someBrokenPlugin"])

    def test_attempted_select_raises(self) -> None:
        with self.assertRaises(MutationForbiddenError):
            self.fake.select("pCube1")


class DeterminismTests(unittest.TestCase):
    def test_two_runs_produce_identical_receipt_json(self) -> None:
        first = install_fake()
        _populate(first)
        receipt1 = maya_bridge.inspect_scene(first, _scene_path())
        json1 = maya_bridge.to_json(receipt1)
        uninstall_fake()

        second = install_fake()
        _populate(second)
        receipt2 = maya_bridge.inspect_scene(second, _scene_path())
        json2 = maya_bridge.to_json(receipt2)
        uninstall_fake()

        self.assertEqual(json1, json2)
        self.assertEqual(receipt1["scene_id"], receipt2["scene_id"])

    def test_scene_id_is_deterministic_across_paths(self) -> None:
        first = install_fake()
        _populate(first)
        receipt1 = maya_bridge.inspect_scene(first, _scene_path())
        uninstall_fake()

        second = install_fake()
        _populate(second)
        receipt2 = maya_bridge.inspect_scene(second, _scene_path())
        uninstall_fake()

        self.assertEqual(receipt1["scene_id"], receipt2["scene_id"])

    def test_different_scene_paths_yield_different_scene_ids(self) -> None:
        first = install_fake()
        _populate(first)
        receipt1 = maya_bridge.inspect_scene(first, Path("scenes/hero.ma"))
        uninstall_fake()

        second = install_fake()
        _populate(second)
        receipt2 = maya_bridge.inspect_scene(second, Path("scenes/boss.ma"))
        uninstall_fake()

        self.assertNotEqual(receipt1["scene_id"], receipt2["scene_id"])


class DiagnosticsRedactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_fake()
        _populate(self.fake)

    def tearDown(self) -> None:
        uninstall_fake()

    def test_absolute_path_redacted(self) -> None:
        absolute = Path("/private/tmp/secret/scene.ma")
        receipt = maya_bridge.inspect_scene(self.fake, absolute)
        view = maya_bridge.diagnostics_for(receipt)
        self.assertEqual(view["scene_path"], "<redacted-path>")

    def test_relative_path_kept(self) -> None:
        receipt = maya_bridge.inspect_scene(self.fake, Path("relative/scene.ma"))
        view = maya_bridge.diagnostics_for(receipt)
        self.assertEqual(view["scene_path"], "relative/scene.ma")


class FrameRangeRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_fake()
        _populate(self.fake)
        self.fake.playback_range = (240, 1)

    def tearDown(self) -> None:
        uninstall_fake()

    def test_inverted_playback_range_rejected(self) -> None:
        with self.assertRaises(maya_bridge.SceneNotAuthorizedError):
            maya_bridge.inspect_scene(self.fake, _scene_path())


class NoCamerasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_fake()
        # Deliberately no cameras.

    def tearDown(self) -> None:
        uninstall_fake()

    def test_empty_camera_list_rejected(self) -> None:
        with self.assertRaises(maya_bridge.SceneNotAuthorizedError):
            maya_bridge.inspect_scene(self.fake, _scene_path())


if __name__ == "__main__":
    unittest.main()
