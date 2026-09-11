# Codex Maya Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build reversible Maya scene inspection and preview export workflows for Codex.

**Architecture:** Skills call a safe Python runner, which launches a user-installed Maya/mayapy process and a narrow scene bridge. The bridge returns structured receipts and never uploads remotely.

**Tech Stack:** Codex plugin manifest, Agent Skills, Python, Maya Python API, JSON Schema, unittest/pytest, optional ffprobe.

**Spec:** `docs/superpowers/specs/2026-09-11-codex-maya-plugin-design.md`

## Global Constraints

- Plugin ID is `codex-maya`; no automatic installations.
- Use argv arrays and allowlisted environment variables.
- Default to untrusted scene scripts/modules disabled.
- Restore all temporary state and never retry Playblast automatically.
- Runtime compatibility requires actual Maya evidence.

### Task 1: Manifest and shared receipts

- [ ] Write failing identity and schema tests.
- [ ] Add `.codex-plugin/plugin.json` plus scene/artifact schemas.
- [ ] Run tests and plugin validation; commit `feat: define Maya plugin contracts`.

### Task 2: Maya capability probe

- [ ] Write failing tests for executable, mayapy, version, ABI, modules, Unicode paths, and environment allowlist.
- [ ] Implement the probe without installation or shell strings.
- [ ] Run focused tests; commit `feat: probe Maya runtime capabilities`.

### Task 3: Scene inspection bridge

- [ ] Create fake `maya.cmds` tests for cameras, timeline, selection, panels, materials, and references.
- [ ] Confirm RED, implement read-only `inspect_scene()`, and confirm no mutation.
- [ ] Commit `feat: inspect Maya scenes`.

### Task 4: Reversible Playblast

- [ ] Write failure-first tests for white-model/material modes and restoration after injected errors.
- [ ] Implement snapshot/configure/playblast/restore in `finally`.
- [ ] Assert pre/post state equality; commit `feat: export reversible Maya previews`.

### Task 5: Media validation

- [ ] Write failing codec/dimension/fps/duration/size/hash tests.
- [ ] Implement dependency-aware validation without installs.
- [ ] Run regression tests; commit `feat: validate Maya artifacts`.

### Task 6: Skills and diagnostics

- [ ] Baseline unsafe agent scenarios for module install, scene scripts, and unverified completion.
- [ ] Create and individually validate `codex-maya-use`, `codex-maya-inspect`, `codex-maya-export-preview`, and `codex-maya-diagnose`.
- [ ] Run TRACE and forward scenarios; commit `feat: add Codex Maya workflows`.

### Task 7: Distribution and runtime gate

- [ ] Add failing marketplace/distribution tests, then implement repository marketplace and validator.
- [ ] Run offline suite, secret scan, link checks, plugin validation, and `git diff --check`.
- [ ] Run authorized real-Maya fixtures or mark the matrix blocked with exact missing evidence.
- [ ] Commit `test: verify Codex Maya distribution`.

---

## Detailed executor contract

### Task 1 — identity and shared receipts

**Files:** `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `schemas/scene_receipt.schema.json`, `schemas/artifact_receipt.schema.json`, `tests/test_contracts.py`, `scripts/validate_distribution.py`.

- [ ] Write RED tests for ID `codex-maya`, display name `Codex Maya`, closed schemas, SHA-256 format, media fields, and restoration status.
- [ ] Implement version `0.1.0` design contracts compatible with `codex-dreamina-3d` artifact receipt v1.
- [ ] Run `python3 -m unittest tests/test_contracts.py -v` and plugin validation; commit Task 1 only.

### Task 2 — Maya runtime probe

**Files:** `scripts/maya_runner.py`, `tests/test_maya_runner.py`.

```python
@dataclass(frozen=True)
class MayaRuntime:
    maya: Path | None
    mayapy: Path
    version: str
    python_version: str
    module_paths: tuple[Path, ...]

def discover_maya(explicit_root: str | None, search_path: str) -> MayaRuntime: ...
def build_batch_argv(runtime: MayaRuntime, request_path: Path) -> list[str]: ...
```

- [ ] RED-test macOS/Windows executable layouts, Maya 2022-style Python 3.7 metadata, Unicode/spaced paths, missing mayapy, and incompatible module paths.
- [ ] Prove subprocess calls use argv, `shell=False`, environment allowlists, timeout, termination, and no installer.
- [ ] Implement capability discovery and stable errors; run focused tests and commit.

### Task 3 — scene inspection

**Files:** `scripts/maya_bridge.py`, `tests/fakes/fake_maya_cmds.py`, `tests/test_scene_inspection.py`.

```python
def inspect_scene(cmds, approved_scene: Path) -> dict: ...
```

- [ ] Build fakes for cameras, playback range, current time, resolution, model panels, display modes, materials, references, namespaces, callbacks, and unknown plug-ins.
- [ ] RED-test that inspection neither changes selection/current time nor loads plug-ins.
- [ ] Implement read-only inspection and one JSON stdout receipt; redact absolute paths in diagnostics.
- [ ] Run twice for deterministic output; commit.

### Task 4 — reversible Playblast

**Files:** modify `scripts/maya_bridge.py`; create `tests/test_playblast.py`.

```python
@contextmanager
def restored_maya_state(cmds): ...
def export_playblast(cmds, request: dict) -> dict: ...
```

- [ ] RED-test white-model, material-preview and existing-video modes plus failure injection at configuration, capture, conversion, validation and publication.
- [ ] Snapshot selection, current time, playback range, camera, active panel, displayAppearance, displayTextures, renderer, image format, resolution and temporary shader overrides.
- [ ] Implement temporary-directory output and atomic publication; existing-video mode performs no scene mutation.
- [ ] Assert pre/post state equality for success, exception, cancellation and timeout; commit.

### Task 5 — dependency and media diagnostics

**Files:** `scripts/media_probe.py`, `scripts/maya_diagnostics.py`, `tests/test_media_probe.py`, `tests/test_maya_diagnostics.py`.

- [ ] RED-test missing module, wrong Python ABI, non-ASCII path, misplaced module/package, missing codec tool and invalid H.264 media.
- [ ] Implement diagnostics that report exact observed version/path category without dumping environment variables.
- [ ] Never mutate Maya module paths or install packages automatically.
- [ ] Validate file stability between probe and hash; run all Python tests and commit.

### Task 6 — Agent Skills

**Files:** `skills/codex-maya-use/`, `skills/codex-maya-inspect/`, `skills/codex-maya-export-preview/`, `skills/codex-maya-diagnose/`, `tests/scenarios/`.

- [ ] Capture no-skill baselines for silent module install, automatic plug-in loading, path misdiagnosis, render retry, and false completion.
- [ ] Implement and validate one Skill at a time; descriptions must distinguish inspection, export and diagnosis.
- [ ] Run quick validation, strict TRACE and fresh-context forward scenarios after each Skill.
- [ ] Verify `codex-maya-use` routes without duplicating detailed workflows; commit.

### Task 7 — distribution and runtime matrix

**Files:** `tests/test_distribution.py`, `docs/verification/offline.md`, `docs/verification/maya-runtime.md`.

- [ ] Test GitHub source, plugin identity/version, four Skills, schemas, references, no symlinks, and no secret-like content.
- [ ] Run the entire offline suite, quick validation, plugin validator, relative-link audit and `git diff --check`.
- [ ] With an explicitly authorized Maya runtime, test a fixture scene on the observed Maya/Python/OS combination; otherwise record the precise runtime blocker.
- [ ] Confirm output receipt compatibility against the same fixtures used by `codex-dreamina-3d`.
- [ ] Install locally only after green distribution tests and record source/cache parity; commit.

## Completion gate

```text
contract_tests = PASS
maya_probe_tests = PASS
scene_tests = PASS
playblast_restoration_tests = PASS
diagnostic_and_media_tests = PASS
skill_quick_validation = 4/4
skill_trace = 4/4
plugin_validation = PASS
secret_matches = 0
runtime_matrix = observed evidence or explicit blocker
```
