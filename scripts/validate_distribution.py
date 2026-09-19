#!/usr/bin/env python3
"""Validate a compatibility-first Codex plugin foundation."""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover - validator must run before Skill workflows
    Draft202012Validator = None
    SchemaError = Exception

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_PATTERNS = (
    re.compile(rb"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
REQUIRED_FILES = (
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "NOTICE",
    "PRIVACY.md",
    "TERMS.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/portable-migration.md",
)
REQUIRED_DIRECTORIES = ("assets", "skills", "schemas", "scripts", "tests")
SHARED_SCHEMAS = (
    "schemas/scene_receipt.schema.json",
    "schemas/artifact_receipt.schema.json",
)


def load_json(target: Path) -> dict:
    return json.loads(target.read_text(encoding="utf-8"))


def png_shape(target: Path) -> tuple[int, int, int]:
    data = target.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[25]


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / ".codex-plugin" / "plugin.json"
    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    for target in (manifest_path, marketplace_path):
        if not target.is_file():
            errors.append(f"missing {target.relative_to(root)}")
    if errors:
        return errors

    manifest = load_json(manifest_path)
    marketplace = load_json(marketplace_path)
    plugin_id = manifest.get("name", "")
    repository = manifest.get("repository", "")
    if NAME_PATTERN.fullmatch(plugin_id) is None:
        errors.append("manifest name must be a kebab-case identifier")
    release_version = str(manifest.get("version", "")).split("+", 1)[0]
    if not release_version:
        errors.append("foundation version must be present")
    if manifest.get("skills") != "./skills/":
        errors.append("manifest skills path must be ./skills/")
    if "mcpServers" in manifest or (root / ".mcp.json").exists():
        errors.append("MCP configuration is forbidden until an MCP server exists")
    interface = manifest.get("interface", {})
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category", "brandColor", "composerIcon", "logo", "logoDark"):
        if not interface.get(field):
            errors.append(f"missing interface.{field}")
    prompts = interface.get("defaultPrompt", [])
    if not 1 <= len(prompts) <= 3 or any(len(item) > 128 for item in prompts):
        errors.append("defaultPrompt must contain 1-3 entries of at most 128 characters")

    entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == plugin_id]
    if len(entries) != 1:
        errors.append("marketplace must contain exactly one matching plugin")
    else:
        expected_source = {"source": "url", "url": repository + ".git", "ref": "main"}
        if entries[0].get("source") != expected_source:
            errors.append("marketplace source does not match repository")
        expected_policy = {"installation": "AVAILABLE", "authentication": "ON_USE"}
        if entries[0].get("policy") != expected_policy:
            errors.append("marketplace policy mismatch")

    for directory in REQUIRED_DIRECTORIES:
        if not (root / directory).is_dir():
            errors.append(f"missing directory: {directory}")
    for filename in REQUIRED_FILES:
        if not (root / filename).is_file():
            errors.append(f"missing required file: {filename}")
    if (root / "plugin.json").exists() or (root / "mcp.json").exists():
        errors.append("portable manifests must remain inactive during compatibility-first scaffolding")

    expected_assets = {
        "assets/official-logo.png": (1024, 1024, 6),
        "assets/composer-icon.png": (256, 256, 6),
    }
    for filename, expected in expected_assets.items():
        target = root / filename
        try:
            if png_shape(target) != expected:
                errors.append(f"invalid PNG shape or alpha channel: {filename}")
        except (OSError, ValueError):
            errors.append(f"missing or invalid PNG: {filename}")

    for target in root.rglob("*"):
        if not target.is_file() or ".git" in target.parts:
            continue
        data = target.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            errors.append(f"secret-like content detected: {target.relative_to(root)}")

    if Draft202012Validator is None:
        errors.append("jsonschema is required to validate shared receipt schemas (install requirements-dev.txt)")
        return errors

    for relative in SHARED_SCHEMAS:
        target = root / relative
        if not target.is_file():
            errors.append(f"missing shared schema: {relative}")
            continue
        try:
            schema = json.loads(target.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except (json.JSONDecodeError, SchemaError) as exc:
            errors.append(f"invalid JSON Schema 2020-12 in {relative}: {exc}")
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors = validate(root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    manifest = load_json(root / ".codex-plugin" / "plugin.json")
    print(f"validated {manifest['name']} compatibility foundation {manifest['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
