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

---

## Revision 2 (2026-09-12): reuse-based Jimeng integration

The original no-vendor/no-upload boundary is superseded. The official
`jimeng_maya_uploader` already owns material detection, Playblast capture, ffmpeg conversion,
protocol limits, loopback bridge creation, and Jimeng link generation. Codex must reuse those
modules byte-for-byte rather than implement a second pipeline.

Both official user flows are in scope: camera Playblast and existing local video. A caller must
set `authorize_upload=true` before a loopback bridge is started. The stable artifact receipt
remains token-free; the ready Jimeng URL is returned separately as ephemeral response data.
Paid generation and browser/account automation remain out of scope.
