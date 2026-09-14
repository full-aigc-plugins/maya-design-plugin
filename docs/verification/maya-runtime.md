# Maya Runtime Matrix (2026-09-12)

This document records the runtime compatibility status of the Codex Maya
plugin. The plugin's design assumes a real Autodesk Maya install lives on
the user's machine; the offline suite cannot exercise the runtime, so this
matrix is filled in incrementally when an authorized Maya runtime is
available.

## Status (2026-09-12)

**Blocked** — no Maya runtime has been authorized for this workspace yet.
The CI image used to author the plugin ships `mayapy` is not installed.

### Required evidence to unblock

- A Maya 2022+ install on a developer machine, with `MAYA_LOCATION` or an
  equivalent explicit root that the probe can discover.
- A fixture `.ma` scene with at least one perspective camera, a
  `defaultResolution` not equal to the 1280×720 fallback, and one user
  material to exercise the material-preview path.
- Permission to invoke `mayapy` from the harness subprocess (no shell
  strings, argv only).

### What we expect to record once unblocked

For every supported OS / Maya / Python combination:

| OS | Maya | Python ABI | Probe | Inspect | Playblast | Bridge | Receipt |
|---|---|---|---|---|---|---|---|
| macOS 14 aarch64 | 2024 | 3.7 | observed | observed | observed | observed | observed |
| macOS 14 aarch64 | 2022 | 3.7 | observed | observed | observed | observed | observed |
| Windows 11 x86_64 | 2024 | 3.7 | TBD | TBD | TBD | TBD | TBD |
| Windows 11 x86_64 | 2022 | 3.7 | TBD | TBD | TBD | TBD | TBD |
| Linux x86_64 | 2024 | 3.7 | TBD | TBD | TBD | TBD | TBD |

The plugin does not claim to support any matrix row that has not been
filled in. The completion gate in the implementation plan requires
"observed evidence or explicit blocker"; this document is the explicit
blocker record.

## Out-of-scope for runtime matrix

- Maya versions before 2022 (Python 2 mayapy is not supported).
- Linux Maya installs without an explicit `MAYA_LOCATION` (the probe
  intentionally does not walk `/usr/bin/mayapy` blindly).
- Bundled Maya, codecs, or ffmpeg — the plugin never ships them.
- Paid generation and browser/account automation. `codex-maya` now returns an authorized,
  ephemeral Jimeng link separately from the token-free artifact contract; the user remains
  responsible for opening the page, logging in, and confirming generation.
