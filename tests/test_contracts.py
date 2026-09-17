"""Contract tests for the Autodesk Maya Design plugin foundation.

These tests guard the shared identity, schemas, and receipt shapes that the rest
of the plugin (probe, bridge, Playblast, media diagnostics, Skills, distribution)
depends on. Schemas are locked here so later tasks cannot widen them by accident.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = "maya-design"
DISPLAY_NAME = "Autodesk Maya Design"
SCHEMA_VERSION = "1.0.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
UUID_V4_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def load_json(relative: str) -> dict:
    target = ROOT / relative
    if not target.is_file():
        raise AssertionError(f"missing contract file: {relative}")
    return json.loads(target.read_text(encoding="utf-8"))


def valid_scene_receipt() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": PLUGIN_ID,
        "scene_id": "11111111-1111-4111-8111-111111111111",
        "scene_path": "scenes/hero.ma",
        "approved_camera": "camera1",
        "frame_range": {"start": 1, "end": 240, "current": 1},
        "resolution": {"width": 1920, "height": 1080},
        "display_mode": "white_model",
        "materials": [],
        "references": [],
        "namespaces": [],
        "callbacks": [],
        "unknown_plugins": [],
        "inspection_status": "ok",
    }


def valid_artifact_receipt() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": PLUGIN_ID,
        "artifact_id": "22222222-2222-4222-8222-222222222222",
        "scene_id": "11111111-1111-4111-8111-111111111111",
        "media_path": "previews/hero.mp4",
        "media_format": "video/mp4",
        "media_sha256": "0" * 64,
        "duration_seconds": 10.0,
        "frame_rate": 24.0,
        "width": 1920,
        "height": 1080,
        "file_size_bytes": 1024,
        "restoration_status": "restored",
        "display_mode": "white_model",
    }


class SchemaShapeTests(unittest.TestCase):
    def test_schemas_are_valid_draft_2020_12(self) -> None:
        for filename in (
            "schemas/scene_receipt.schema.json",
            "schemas/artifact_receipt.schema.json",
        ):
            with self.subTest(filename=filename):
                schema = load_json(filename)
                try:
                    Draft202012Validator.check_schema(schema)
                except SchemaError as exc:
                    self.fail(f"{filename} is not a valid JSON Schema 2020-12: {exc}")


class PluginIdentityTests(unittest.TestCase):
    def test_manifest_identity(self) -> None:
        manifest = load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["name"], PLUGIN_ID)
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertEqual(manifest["interface"]["displayName"], DISPLAY_NAME)
        self.assertEqual(manifest["interface"]["brandColor"], "#14B8A6")
        self.assertNotIn("mcpServers", manifest)


class SceneReceiptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = Draft202012Validator(load_json("schemas/scene_receipt.schema.json"))

    def test_minimal_valid_receipt_passes(self) -> None:
        errors = sorted(self.validator.iter_errors(valid_scene_receipt()), key=lambda e: e.path)
        self.assertEqual(errors, [])

    def test_missing_required_field_rejected(self) -> None:
        receipt = valid_scene_receipt()
        receipt.pop("approved_camera")
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors, "expected validation error for missing required field")

    def test_unknown_display_mode_rejected(self) -> None:
        receipt = valid_scene_receipt()
        receipt["display_mode"] = "wireframe"
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)

    def test_schema_version_must_match(self) -> None:
        receipt = valid_scene_receipt()
        receipt["schema_version"] = "0.9.0"
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)

    def test_frame_range_shape_permits_inversion(self) -> None:
        receipt = valid_scene_receipt()
        receipt["frame_range"] = {"start": 240, "end": 1, "current": 1}
        # Schema accepts any non-negative integers; the bridge (Task 3) enforces the
        # start <= end business rule. Asserting this here pins the contract split:
        # schema = shape, bridge = rule.
        errors = list(self.validator.iter_errors(receipt))
        self.assertEqual(errors, [], "schema permits the shape; bridge enforces inversion")

    def test_additional_properties_rejected_on_frame_range(self) -> None:
        receipt = valid_scene_receipt()
        receipt["frame_range"]["step"] = 1
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors, "frame_range.additionalProperties must be closed")

    def test_additional_top_level_property_rejected(self) -> None:
        receipt = valid_scene_receipt()
        receipt["plugin_quirk"] = "anything"
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors, "top-level additionalProperties must be closed")


class ArtifactReceiptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = Draft202012Validator(load_json("schemas/artifact_receipt.schema.json"))

    def test_minimal_valid_receipt_passes(self) -> None:
        errors = sorted(self.validator.iter_errors(valid_artifact_receipt()), key=lambda e: e.path)
        self.assertEqual(errors, [])

    def test_sha256_must_be_lowercase_hex(self) -> None:
        receipt = valid_artifact_receipt()
        receipt["media_sha256"] = "A" * 64
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)
        receipt["media_sha256"] = "abc"  # wrong length
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)

    def test_media_format_locked_to_mp4(self) -> None:
        receipt = valid_artifact_receipt()
        receipt["media_format"] = "video/quicktime"
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)

    def test_restoration_status_enum_enforced(self) -> None:
        receipt = valid_artifact_receipt()
        receipt["restoration_status"] = "skipped"
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)

    def test_missing_restoration_status_rejected(self) -> None:
        receipt = valid_artifact_receipt()
        receipt.pop("restoration_status")
        errors = list(self.validator.iter_errors(receipt))
        self.assertTrue(errors)


class Sha256RegexTests(unittest.TestCase):
    def test_known_digest_matches(self) -> None:
        digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertTrue(bool(SHA256_PATTERN.fullmatch(digest)))

    def test_uppercase_hex_rejected(self) -> None:
        self.assertFalse(bool(SHA256_PATTERN.fullmatch("A" * 64)))

    def test_short_hex_rejected(self) -> None:
        self.assertFalse(bool(SHA256_PATTERN.fullmatch("a" * 63)))


class UuidShapeTests(unittest.TestCase):
    def test_uuid_v4_pattern_matches(self) -> None:
        self.assertTrue(bool(UUID_V4_PATTERN.fullmatch("11111111-1111-4111-8111-111111111111")))

    def test_uuid_v1_rejected(self) -> None:
        # Version nibble = 1, not 4
        self.assertFalse(bool(UUID_V4_PATTERN.fullmatch("11111111-1111-1111-8111-111111111111")))


if __name__ == "__main__":
    unittest.main()
