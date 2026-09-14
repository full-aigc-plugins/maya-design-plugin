# Offline Verification (2026-09-12)

The Codex Maya plugin ships a hermetic offline suite that exercises every
component without invoking a real Maya install. This document records the
exact commands and expected outputs.

## Commands

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_distribution.py .
python3 scripts/validate_distribution.py docs/..
git diff --check
```

The first command runs every contract, probe, scene, playblast, media,
diagnostics, skills, and distribution test. The second runs the
distribution validator. The third is a sanity check that the validator
accepts the repository from any cwd. The fourth fails the build on any
trailing-whitespace or no-newline-at-EOF regression.

## Expected results

- All tests pass.
- `validate_distribution.py` prints `validated codex-maya compatibility foundation 0.1.0`.
- `git diff --check` exits 0.

## What the offline suite does NOT cover

- Real Maya discovery (`MAYA_NOT_FOUND` / `ABI_MISMATCH` are observed in the
  test for the failure path, not the happy path).
- Real Playblast capture, conversion, validation, and publication.
- Real browser hand-off and Jimeng Web import. Offline tests cover the returned link contract,
  not the browser's ability to fetch the video from the loopback bridge.

These are gated by `docs/verification/maya-runtime.md`.

## Coverage map

| Layer | Test file |
|---|---|
| Plugin contracts | `tests/test_contracts.py` |
| Maya discovery (argv, env allowlist) | `tests/test_maya_runner.py` |
| Scene inspection (no mutation) | `tests/test_scene_inspection.py` |
| Playblast + reversible state + vendor integrity | `tests/test_playblast.py` |
| Media validation + diagnostics | `tests/test_media_probe.py`, `tests/test_maya_diagnostics.py` |
| Skills validation | `tests/test_skills.py` |
| Distribution identity + structure | `tests/test_distribution.py` |
| Extended distribution (links, secrets, vendor) | `tests/test_distribution_extended.py` |
| **Official plugin-format conformance** | `tests/test_codex_plugin_compliance.py` |

## Plugin-format conformance

`tests/test_codex_plugin_compliance.py` (39 tests) encodes the requirements from
the official authoring page, <https://developers.openai.com/plugins/build/plugins>.
Each test names the requirement it covers, so the claim can be checked against
the doc rather than trusted.

Where the doc explicitly leaves something unspecified, the tests assert the
weaker property instead of inventing a rule:

- `policy.authentication` — the doc says "values not enumerated", so the test
  asserts it is a non-empty string. The value this repository uses, `ON_USE`,
  matches the PartMe family distribution marketplaces and is one of the two
  values observed in the marketplaces registered on this machine.
- Symlink rules, file-size, and file-count limits are not stated on that page
  and are not invented here. `tests/test_distribution_extended.py` still asserts
  no symlinks, because that was already established for this repository family.

### Ground truth used

The format was checked against two independent sources of working examples, not
only against the prose:

1. OpenAI's own plugins installed on this machine
   (`~/.codex/plugins/cache/openai-bundled/*`, `openai-curated-remote/*`) — all
   use `.codex-plugin/plugin.json` with a top-level `interface` object.
2. The PartMe family siblings (`~/.codex/plugins/cache/personal/codex-dreamina-3d`,
   and `codex-blender-plugin`'s marketplace) — same field set, same
   `partme-ai-<dcc>` marketplace naming, same `url` source with `ref: main`.

### Not covered offline

A live `codex plugin marketplace add` / install round-trip. The `codex` binary
is not installed in this environment, so package loading by the real CLI is
unverified here and is recorded as such.
