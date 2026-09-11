"""Validate the four Codex Maya Agent Skills.

Tests are static and hermetic: they parse each `SKILL.md`'s frontmatter,
assert required keys, and assert that the description text distinguishes
the Skill from its siblings. This is the minimum quick-validation step
that every Skill must pass before the strict TRACE / forward-scenario
runs in production.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"

REQUIRED_SKILLS = (
    "codex-maya-use",
    "codex-maya-inspect",
    "codex-maya-export-preview",
    "codex-maya-diagnose",
)

FRONTMATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---\n", re.DOTALL)


def _parse_skill(name: str) -> tuple[dict[str, str], str]:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.is_file():
        raise AssertionError(f"missing Skill: {path}")
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise AssertionError(f"{path} has no frontmatter block")
    body_lines = match.group("body").splitlines()
    frontmatter: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []
    for line in body_lines:
        if current_key is None:
            if ":" not in line:
                continue
            key, _, rest = line.partition(":")
            current_key = key.strip()
            rest = rest.strip()
            # YAML pipe syntax: `key: |` then indented lines follow.
            if rest == "|" or rest == ">":
                current_value_lines = []
                continue
            frontmatter[current_key] = rest
            current_key = None
            continue
        # Indented continuation lines belong to the previous key.
        if line.startswith((" ", "\t")):
            current_value_lines.append(line.strip())
            continue
        # End of block-style value: flush and start a new key.
        frontmatter[current_key] = " ".join(current_value_lines).strip()
        current_key = None
        current_value_lines = []
        if ":" in line:
            key, _, rest = line.partition(":")
            current_key = key.strip()
            rest = rest.strip()
            if rest == "|" or rest == ">":
                current_value_lines = []
                continue
            frontmatter[current_key] = rest
            current_key = None
    if current_key is not None:
        frontmatter[current_key] = " ".join(current_value_lines).strip()
    return frontmatter, text


class SkillFileTests(unittest.TestCase):
    def test_all_required_skills_exist(self) -> None:
        for name in REQUIRED_SKILLS:
            self.assertTrue((SKILLS_DIR / name / "SKILL.md").is_file(), name)

    def test_each_skill_has_required_frontmatter(self) -> None:
        for name in REQUIRED_SKILLS:
            with self.subTest(skill=name):
                fm, _ = _parse_skill(name)
                self.assertEqual(fm["name"], name)
                self.assertIn("description", fm)
                self.assertGreater(len(fm["description"].strip()), 32)

    def test_description_under_1500_chars(self) -> None:
        for name in REQUIRED_SKILLS:
            with self.subTest(skill=name):
                fm, _ = _parse_skill(name)
                self.assertLessEqual(len(fm["description"]), 1500)


class SkillDistinctnessTests(unittest.TestCase):
    """Ensure each Skill's description mentions unique trigger words."""

    def _descs(self) -> dict[str, str]:
        return {name: _parse_skill(name)[0]["description"].lower() for name in REQUIRED_SKILLS}

    def test_inspect_description_mentions_inspection(self) -> None:
        descs = self._descs()
        self.assertIn("inspect", descs["codex-maya-inspect"])

    def test_export_description_mentions_export(self) -> None:
        descs = self._descs()
        self.assertIn("export", descs["codex-maya-export-preview"])
        self.assertIn("playblast", descs["codex-maya-export-preview"])

    def test_diagnose_description_mentions_diagnose(self) -> None:
        descs = self._descs()
        self.assertIn("diagnos", descs["codex-maya-diagnose"])

    def test_use_description_references_other_skills(self) -> None:
        descs = self._descs()
        # The router must explicitly mention its three delegation targets so
        # it never duplicates their workflows in its own body.
        for target in (
            "codex-maya-inspect",
            "codex-maya-export-preview",
            "codex-maya-diagnose",
        ):
            self.assertIn(target, descs["codex-maya-use"])


class SkillSafetyTests(unittest.TestCase):
    """Skills must not promise to install software, auto-retry, or mutate Maya."""

    FORBIDDEN_PHRASES = (
        "auto retry",
        "auto-retry",
        "automatically retry",
        "silently install",
        "force install",
    )

    def test_no_skill_promises_automatic_retry(self) -> None:
        for name in REQUIRED_SKILLS:
            with self.subTest(skill=name):
                _, body = _parse_skill(name)
                lowered = body.lower()
                for phrase in self.FORBIDDEN_PHRASES:
                    self.assertNotIn(phrase, lowered, f"{name}: forbids {phrase!r}")

    def test_export_skill_explicitly_disclaims_auto_retry(self) -> None:
        _, body = _parse_skill("codex-maya-export-preview")
        self.assertIn("never retries", body.lower())

    def test_diagnose_skill_explicitly_disclaims_installing(self) -> None:
        _, body = _parse_skill("codex-maya-diagnose")
        self.assertIn("no `pip install`", body.lower())

    def test_inspect_skill_explicitly_disclaims_mutation(self) -> None:
        _, body = _parse_skill("codex-maya-inspect")
        self.assertIn("no plug-in loading", body.lower())


class SkillAntiRoutingTests(unittest.TestCase):
    def test_router_does_not_duplicate_workflow_instructions(self) -> None:
        """The router's body must defer workflow detail to the dedicated Skills."""

        _, body = _parse_skill("codex-maya-use")
        # The router must not contain the specific export workflow header.
        self.assertNotIn("# Implementation", body)
        # It must, however, list the routing targets.
        for target in ("inspect", "export", "diagnose"):
            self.assertIn(target, body.lower())


if __name__ == "__main__":
    unittest.main()
