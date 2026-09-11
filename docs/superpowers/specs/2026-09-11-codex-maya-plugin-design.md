# Codex Maya Plugin Design

## Goal

Build a local-only Codex plugin that inspects Maya scenes and exports validated, reversible preview video artifacts.

## Requirements

- Discover Maya and ABI/module compatibility without installation.
- Produce read-only scene receipts before mutation.
- Export white-model and material-aware Playblast from an approved camera/range.
- Restore every modified Maya state after every terminal outcome.
- Emit the shared artifact receipt used by `codex-dreamina-3d`.

## Non-goals

No Dreamina upload, paid generation, vendor source reuse, arbitrary plug-in loading, bundled Maya, or bundled codec runtime.

## Acceptance

Offline unit/fixture tests and plugin validation must pass. Real Maya compatibility remains blocked until an authorized runtime matrix is executed.
