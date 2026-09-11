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
