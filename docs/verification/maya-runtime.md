# Maya Runtime Matrix (2026-09-12)

This document records the runtime compatibility status of the Codex Maya
plugin. The plugin's design assumes a real Autodesk Maya install lives on
the user's machine; the offline suite cannot exercise the runtime, so this
matrix is filled in incrementally when an authorized Maya runtime is
available.

## Status (2026-09-12)

**Blocked** — no Maya runtime has been authorized for this workspace yet.
`mayapy` is not installed (verified: no `/Applications/Autodesk`, no
`maya`/`mayapy` on `PATH`, `MAYA_LOCATION` unset).

The **driver is no longer part of this blocker.** It is implemented and
covered by `tests/test_maya_driver.py`, which runs the real
`scripts/maya_request.py` against a real `subprocess` boundary with only
`maya.cmds` faked. See the "Driver status" section below for what that does
and does not prove.

### Required evidence to unblock

- A Maya 2022+ install on a developer machine, with `MAYA_LOCATION` or an
  equivalent explicit root that the probe can discover.
- A fixture `.ma` scene with at least one perspective camera, a
  `defaultResolution` not equal to the 1280×720 fallback, and one user
  material to exercise the material-preview path.
- Permission to invoke `mayapy` from the harness subprocess (no shell
  strings, argv only).

## Driver status (2026-09-12)

`python3 scripts/maya_runner.py <inspect|export|jimeng-flow> ...` is the
supported entrypoint. It discovers Maya, launches `mayapy` with an argv array
and an allowlisted environment, bounds the child with a timeout, terminates it
on expiry, and maps failures to stable error codes.

### What the offline driver tests do prove

| Property | Evidence |
|---|---|
| Request/response file protocol round trip | `InspectRoundTripTests` runs the real runner end to end |
| A real receipt comes back over the boundary | `test_inspect_with_seeded_scene_returns_receipt_fields` |
| In-Maya error codes survive verbatim | `ErrorCodePropagationTests` (`PLAYBLAST_FAILED`, `RESTORE_UNCONFIRMED`) |
| Timeout terminates the child | `TimeoutAndTerminationTests` asserts the recorded child pid is gone |
| A silent death is a crash, not a success | `CrashHandlingTests` (non-zero exit, corrupt response) |
| Only allowlisted env reaches the child | `EnvironmentIsolationTests` pins the exact `PATH` value the child sees |
| The runner stays Python 3.7-compatible | `MayaRequestModuleTests` (no walrus, lazy `maya.cmds`) |

### What it still does NOT prove

`maya.cmds` is faked. Nothing here demonstrates that Maya accepts the
Playblast arguments, that `ViewportPreviewState` restores a real scene, or
that the vendored ffmpeg conversion produces a playable H.264 file. Those
remain in the runtime matrix above and require the real install.

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
