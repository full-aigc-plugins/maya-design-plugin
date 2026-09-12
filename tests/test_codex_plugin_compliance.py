"""Conformance tests against the official Codex plugin authoring docs.

Source of truth: https://developers.openai.com/plugins/build/plugins

Each test names the documented requirement it encodes so a future reader can
check the claim against the doc rather than trusting this file. Requirements
that the doc explicitly leaves unspecified (symlink rules, size limits,
exhaustive enum lists) are *not* invented here; where the doc says "values not
enumerated" the test asserts the value is a non-empty string instead of
guessing an enum.

This file complements, and does not replace:
  tests/test_distribution.py          -- foundation identity/structure
  tests/test_distribution_extended.py -- links, secrets, symlinks, vendor
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SKILLS_DIR = ROOT / "skills"

KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
URL_RE = re.compile(r"^https?://")

# Doc: "Policy.installation" -- the three values the page shows.
INSTALLATION_VALUES = {"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"}

# Doc lists these `interface` members. `logoDark` is present in this
# repository's family baseline but absent from OpenAI's own manifests, so it is
# treated as an accepted extension rather than a required field.
DOCUMENTED_INTERFACE_FIELDS = (
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "defaultPrompt",
    "brandColor",
    "composerIcon",
    "logo",
    "screenshots",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestLocationTests(unittest.TestCase):
    """Doc: root `plugin.json` is the portable manifest; `.codex-plugin/plugin.json`
    is the supported compatibility fallback. This package ships the fallback."""

    def test_uses_the_supported_compatibility_manifest(self) -> None:
        self.assertTrue(MANIFEST.is_file(), "missing .codex-plugin/plugin.json")

    def test_portable_manifest_is_deliberately_absent(self) -> None:
        # Documented decision in docs/portable-migration.md: portable root
        # manifests stay inactive until both formats can be kept in sync.
        self.assertFalse((ROOT / "plugin.json").exists())
        self.assertFalse((ROOT / "mcp.json").exists())

    def test_portable_components_sit_at_the_plugin_root(self) -> None:
        # Doc: "Keep plugin.json, mcp.json, skills/, and assets/ at the plugin root."
        for name in ("skills", "assets"):
            self.assertTrue((ROOT / name).is_dir(), f"{name}/ must be at plugin root")


class ManifestIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load(MANIFEST)

    def test_name_is_stable_kebab_case(self) -> None:
        # Doc: "Use a stable plugin `name` in kebab-case"; it doubles as the
        # component namespace.
        name = self.manifest["name"]
        self.assertIsInstance(name, str)
        self.assertRegex(name, KEBAB_RE)

    def test_version_is_a_string(self) -> None:
        # Doc: `version` -- optional string.
        self.assertIsInstance(self.manifest["version"], str)
        self.assertTrue(self.manifest["version"].strip())

    def test_description_is_a_string(self) -> None:
        self.assertIsInstance(self.manifest["description"], str)

    def test_author_is_an_object_with_documented_members(self) -> None:
        # Doc: `author` -- optional object with name, email, url.
        author = self.manifest["author"]
        self.assertIsInstance(author, dict)
        self.assertTrue(set(author).issubset({"name", "email", "url"}), author)
        self.assertIn("name", author)

    def test_homepage_and_repository_are_urls(self) -> None:
        for field in ("homepage", "repository"):
            with self.subTest(field=field):
                self.assertRegex(self.manifest[field], URL_RE)

    def test_license_is_a_string(self) -> None:
        self.assertIsInstance(self.manifest["license"], str)

    def test_keywords_is_an_array_of_strings(self) -> None:
        keywords = self.manifest["keywords"]
        self.assertIsInstance(keywords, list)
        self.assertTrue(all(isinstance(k, str) for k in keywords))
        self.assertTrue(keywords, "keywords should not be empty")


class InterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.interface = load(MANIFEST)["interface"]

    def test_interface_is_an_object(self) -> None:
        self.assertIsInstance(self.interface, dict)

    def test_every_documented_interface_field_is_present(self) -> None:
        missing = [f for f in DOCUMENTED_INTERFACE_FIELDS if f not in self.interface]
        self.assertEqual(missing, [], f"interface is missing documented fields: {missing}")

    def test_capabilities_is_an_array(self) -> None:
        caps = self.interface["capabilities"]
        self.assertIsInstance(caps, list)
        self.assertTrue(all(isinstance(c, str) for c in caps))

    def test_default_prompt_is_an_array_of_strings(self) -> None:
        prompts = self.interface["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertTrue(prompts)
        self.assertTrue(all(isinstance(p, str) for p in prompts))

    def test_brand_color_is_a_hex_string(self) -> None:
        self.assertRegex(self.interface["brandColor"], HEX_COLOR_RE)

    def test_screenshots_is_an_array(self) -> None:
        self.assertIsInstance(self.interface["screenshots"], list)

    def test_privacy_and_terms_are_urls(self) -> None:
        for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
            with self.subTest(field=field):
                self.assertRegex(self.interface[field], URL_RE)


class ManifestAssetResolutionTests(unittest.TestCase):
    """Doc: icon/logo members are paths. A declared path that does not resolve is
    a broken package even though the string itself is well-formed."""

    ASSET_FIELDS = ("composerIcon", "logo", "logoDark")

    def test_declared_asset_paths_start_with_dot_slash(self) -> None:
        interface = load(MANIFEST)["interface"]
        for field in self.ASSET_FIELDS:
            value = interface.get(field)
            if value is None:
                continue
            with self.subTest(field=field):
                self.assertTrue(value.startswith("./"), f"{field}={value!r}")

    def test_declared_asset_paths_resolve_inside_the_plugin_root(self) -> None:
        interface = load(MANIFEST)["interface"]
        for field in self.ASSET_FIELDS:
            value = interface.get(field)
            if value is None:
                continue
            with self.subTest(field=field):
                resolved = (ROOT / value).resolve()
                self.assertTrue(resolved.is_file(), f"{field} -> {resolved} does not exist")
                self.assertTrue(
                    str(resolved).startswith(str(ROOT.resolve())),
                    f"{field} escapes the plugin root",
                )


class SkillsDiscoveryTests(unittest.TestCase):
    """Doc: skills live at `skills/<skill-name>/SKILL.md`; frontmatter requires
    `name` and `description`; portable packages discover skills from the root
    `skills/` directory."""

    def _skill_dirs(self) -> list[Path]:
        return sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())

    def test_skills_discovered_from_root_skills_directory(self) -> None:
        self.assertTrue(SKILLS_DIR.is_dir())
        self.assertTrue(self._skill_dirs(), "no skill directories found")

    def test_every_skill_dir_has_a_skill_md(self) -> None:
        for d in self._skill_dirs():
            with self.subTest(skill=d.name):
                self.assertTrue((d / "SKILL.md").is_file(), f"{d.name} lacks SKILL.md")

    def test_every_skill_declares_name_and_description(self) -> None:
        for d in self._skill_dirs():
            with self.subTest(skill=d.name):
                text = (d / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"), "frontmatter must open the file")
                fm = text.split("---\n", 2)[1]
                keys = {line.split(":", 1)[0].strip() for line in fm.splitlines() if ":" in line}
                self.assertIn("name", keys)
                self.assertIn("description", keys)

    def test_skill_name_matches_its_directory(self) -> None:
        for d in self._skill_dirs():
            with self.subTest(skill=d.name):
                text = (d / "SKILL.md").read_text(encoding="utf-8")
                fm = text.split("---\n", 2)[1]
                declared = None
                for line in fm.splitlines():
                    if line.startswith("name:"):
                        declared = line.split(":", 1)[1].strip()
                        break
                self.assertEqual(declared, d.name)

    def test_skill_names_are_kebab_case(self) -> None:
        for d in self._skill_dirs():
            with self.subTest(skill=d.name):
                self.assertRegex(d.name, KEBAB_RE)


class MarketplaceLocationTests(unittest.TestCase):
    """Doc: repository marketplaces live at `$REPO_ROOT/.agents/plugins/marketplace.json`."""

    def test_marketplace_is_at_the_documented_path(self) -> None:
        self.assertTrue(MARKETPLACE.is_file(), f"missing {MARKETPLACE.relative_to(ROOT)}")


class MarketplaceSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.marketplace = load(MARKETPLACE)

    def test_top_level_name_is_present(self) -> None:
        self.assertIsInstance(self.marketplace.get("name"), str)
        self.assertTrue(self.marketplace["name"].strip())

    def test_optional_interface_display_name(self) -> None:
        interface = self.marketplace.get("interface")
        if interface is not None:
            self.assertIsInstance(interface, dict)
            self.assertIsInstance(interface.get("displayName"), str)

    def test_plugins_is_a_non_empty_array(self) -> None:
        plugins = self.marketplace.get("plugins")
        self.assertIsInstance(plugins, list)
        self.assertTrue(plugins)

    def test_every_entry_has_the_documented_members(self) -> None:
        # Doc: each plugin entry has name, source, policy.installation,
        # policy.authentication, category.
        for entry in self.marketplace["plugins"]:
            with self.subTest(plugin=entry.get("name")):
                self.assertIn("name", entry)
                self.assertIn("source", entry)
                self.assertIn("policy", entry)
                self.assertIn("category", entry)
                self.assertIn("installation", entry["policy"])
                self.assertIn("authentication", entry["policy"])

    def test_installation_uses_a_documented_value(self) -> None:
        for entry in self.marketplace["plugins"]:
            with self.subTest(plugin=entry.get("name")):
                self.assertIn(entry["policy"]["installation"], INSTALLATION_VALUES)

    def test_authentication_is_a_non_empty_string(self) -> None:
        # Doc: "values not enumerated" -- assert presence, do not invent an enum.
        for entry in self.marketplace["plugins"]:
            with self.subTest(plugin=entry.get("name")):
                value = entry["policy"]["authentication"]
                self.assertIsInstance(value, str)
                self.assertTrue(value.strip())

    def test_url_sources_declare_a_git_url(self) -> None:
        for entry in self.marketplace["plugins"]:
            source = entry["source"]
            if source.get("source") != "url":
                continue
            with self.subTest(plugin=entry["name"]):
                self.assertRegex(source["url"], URL_RE)
                self.assertTrue(source["url"].endswith(".git"), source["url"])
                self.assertIsInstance(source.get("ref"), str)

    def test_local_sources_keep_paths_relative_to_the_marketplace_root(self) -> None:
        # Doc: "Keep source.path relative to the marketplace root, start it
        # with `./`, and keep it inside that root."
        for entry in self.marketplace["plugins"]:
            source = entry["source"]
            if source.get("source") != "local":
                continue
            with self.subTest(plugin=entry["name"]):
                path = source["path"]
                self.assertTrue(path.startswith("./"), path)
                self.assertNotIn("..", Path(path).parts)


class PluginIdentityConsistencyTests(unittest.TestCase):
    """The manifest name and the marketplace entry name must agree, because
    enablement keys are `plugin-name@marketplace-name`."""

    def test_marketplace_entry_matches_the_manifest(self) -> None:
        manifest_name = load(MANIFEST)["name"]
        entries = [e for e in load(MARKETPLACE)["plugins"] if e["name"] == manifest_name]
        self.assertEqual(len(entries), 1, "marketplace must list this plugin exactly once")

    def test_repository_matches_the_git_url_source(self) -> None:
        manifest = load(MANIFEST)
        entry = next(
            e for e in load(MARKETPLACE)["plugins"] if e["name"] == manifest["name"]
        )
        source = entry["source"]
        if source.get("source") == "url":
            self.assertEqual(source["url"], manifest["repository"].rstrip("/") + ".git")


class NoBundledMcpTests(unittest.TestCase):
    """Doc: bundled MCP is a root `mcp.json`. This plugin ships no MCP server,
    so both the manifest key and the file must be absent."""

    def test_manifest_has_no_mcp_servers_key(self) -> None:
        self.assertNotIn("mcpServers", load(MANIFEST))

    def test_no_mcp_json_files(self) -> None:
        for name in ("mcp.json", ".mcp.json"):
            with self.subTest(file=name):
                self.assertFalse((ROOT / name).exists())


class NoHooksTests(unittest.TestCase):
    """Doc: `hooks/hooks.json` is discovered by default. This plugin ships no
    hooks, so the file must be absent -- otherwise it would be picked up."""

    def test_no_hooks_file(self) -> None:
        self.assertFalse((ROOT / "hooks" / "hooks.json").exists())

    def test_manifest_declares_no_hooks(self) -> None:
        self.assertNotIn("hooks", load(MANIFEST))


if __name__ == "__main__":
    unittest.main()
