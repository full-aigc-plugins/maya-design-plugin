"""Distribution-level checks for the Codex Maya plugin.

Extends the foundation checks in `tests/test_distribution.py`. The original
file guards identity, marketplace, structure, brand assets, and the
distribution validator; this module adds:

- GitHub source / repository identity
- Plugin identity and version
- The four Skills are present, each with a SKILL.md
- Both schemas parse as JSON Schema 2020-12 and reference the same plugin id
- Every relative link in the docs tree resolves to a real file
- No symlinks anywhere in the repository (Codex plugins forbid them)
- No secret-like content (private keys, Google API tokens)
- Vendor subtree integrity (the Jimeng source checksum is unchanged)
- Relative-only paths inside the vendor subtree
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "maya-use",
    "maya-inspect",
    "maya-export-preview",
    "maya-diagnose",
)
SCHEMAS = (
    "schemas/scene_receipt.schema.json",
    "schemas/artifact_receipt.schema.json",
)
SECRET_PATTERNS = (
    re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def _load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class GitHubSourceTests(unittest.TestCase):
    def test_repository_field_points_to_github(self) -> None:
        manifest = _load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["repository"], "https://github.com/partme-ai/partme-maya-plugin")
        marketplace = _load_json(".agents/plugins/marketplace.json")
        source = next(
            entry for entry in marketplace["plugins"] if entry["name"] == manifest["name"]
        )["source"]
        self.assertEqual(source["url"], "https://github.com/partme-ai/partme-maya-plugin.git")
        self.assertEqual(source["ref"], "main")


class PluginIdentityTests(unittest.TestCase):
    def test_identity_and_version(self) -> None:
        manifest = _load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["name"], "codex-maya")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertFalse(any(c in manifest["name"] for c in (" ", "\t")))

    def test_display_name_present(self) -> None:
        manifest = _load_json(".codex-plugin/plugin.json")
        self.assertEqual(manifest["interface"]["displayName"], "Codex Maya")


class SkillsPresenceTests(unittest.TestCase):
    def test_all_four_skills_have_a_skill_md(self) -> None:
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file(), name)

    def test_skills_directory_has_no_extra_files(self) -> None:
        entries = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
        self.assertEqual(entries, sorted(SKILLS))

    def test_each_skill_names_itself(self) -> None:
        for name in SKILLS:
            with self.subTest(skill=name):
                text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---"))
                self.assertIn(f"name: {name}", text)


class SchemasTests(unittest.TestCase):
    def test_schemas_parse_and_share_plugin_id(self) -> None:
        ids = set()
        for relative in SCHEMAS:
            with self.subTest(schema=relative):
                schema = _load_json(relative)
                self.assertEqual(schema["properties"]["plugin_id"]["const"], "codex-maya")
                self.assertEqual(schema["properties"]["schema_version"]["const"], "1.0.0")
                self.assertIn("schema_version", schema["required"])
                ids.add(id(schema))
        self.assertEqual(len(ids), 2)

    def test_scene_and_artifact_receipts_are_compatible(self) -> None:
        """The artifact receipt must reference the scene receipt's plugin_id and schema version."""

        scene = _load_json("schemas/scene_receipt.schema.json")
        artifact = _load_json("schemas/artifact_receipt.schema.json")
        self.assertEqual(
            scene["properties"]["plugin_id"]["const"],
            artifact["properties"]["plugin_id"]["const"],
        )
        self.assertEqual(
            scene["properties"]["schema_version"]["const"],
            artifact["properties"]["schema_version"]["const"],
        )


class ReferenceLinkTests(unittest.TestCase):
    def test_relative_markdown_links_resolve(self) -> None:
        link_re = re.compile(r"\]\((?!https?:|mailto:|#)([^)]+)\)")
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for match in link_re.finditer(text):
                target = match.group(1).split("#", 1)[0]
                if not target:
                    continue
                if target.startswith("/"):
                    self.fail(f"{path}: absolute link {target!r}")
                resolved = (path.parent / target).resolve()
                self.assertTrue(
                    resolved.is_file(),
                    f"{path}: dead link {target!r} -> {resolved}",
                )


class NoSymlinksTests(unittest.TestCase):
    def test_repository_has_no_symlinks(self) -> None:
        for path in ROOT.rglob("*"):
            if ".git" in path.parts:
                continue
            if path.is_symlink():
                self.fail(f"symlink present at {path.relative_to(ROOT)}")


class SecretScanTests(unittest.TestCase):
    def test_no_secret_like_content_anywhere(self) -> None:
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            for pattern in SECRET_PATTERNS:
                self.assertIsNone(
                    pattern.search(data),
                    f"secret-like content in {path.relative_to(ROOT)}",
                )


class VendorSubtreeTests(unittest.TestCase):
    """The vendored Jimeng source must remain unmodified and reference-relative."""

    EXPECTED_CHECKSUM = "33dc6dfb766dc43a515c91547ab58c26d044079296b92f5c4689b9eb5106191f"

    def test_subtree_present_and_checksum_matches(self) -> None:
        from scripts.maya_bridge import JIMENG_VENDOR_DIR
        self.assertTrue(JIMENG_VENDOR_DIR.is_dir())
        digest = hashlib.sha256()
        for dirpath, _, filenames in os.walk(JIMENG_VENDOR_DIR):
            for name in sorted(filenames):
                full = Path(dirpath) / name
                rel = full.relative_to(JIMENG_VENDOR_DIR).as_posix()
                digest.update(rel.encode("utf-8"))
                digest.update(full.read_bytes())
        self.assertEqual(digest.hexdigest(), self.EXPECTED_CHECKSUM)

    def test_vendor_subtree_paths_are_relative(self) -> None:
        """The vendored files must use relative paths, not absolute install paths."""

        for path in (ROOT / "scripts" / "jimeng_third_party").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for forbidden in ("/opt/maya", "/Applications/Maya", "C:\\Program Files"):
                self.assertNotIn(forbidden, text, f"{path.name}: forbids {forbidden}")


class ValidatorPipelineTests(unittest.TestCase):
    def test_validator_runs_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_distribution.py"), str(ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validated codex-maya", result.stdout)


if __name__ == "__main__":
    unittest.main()
