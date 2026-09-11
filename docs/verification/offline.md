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
- Local-bridge link hand-off to `codex-dreamina-3d`.

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
