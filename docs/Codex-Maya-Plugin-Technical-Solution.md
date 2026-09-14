# Codex Maya Plugin Technical Solution

> **Document control**
>
> | Field | Value |
> |---|---|
> | Status | Offline implementation complete; real-Maya runtime not verified |
> | Scope | How the Maya integration is built, how it restores state, and how it is verified |
> | Audience | Implementers extending or reviewing this plugin |
> | Runtime evidence | `docs/verification/` |

## 1. Decision

Use a Codex Skill layer, an argv-only runner, and a Maya Python bridge supporting batch inspection and controlled Playblast. Do not copy the official Dreamina Maya uploader.

### Alternatives considered

| Alternative | Why it was rejected |
|---|---|
| Copy the official uploader into this repository | Hidden coupling to vendor internals, and the vendor owns its own update cadence |
| Drive Maya through `maya.cmds` from the host Python | The host interpreter is not Maya's interpreter, so the ABI and module paths would not match |
| Validate the MP4 with an external probe | Adds an unverifiable dependency to a media claim |
| Repair the user's Maya environment by installing packages | Mutates a licensed, user-managed installation |
| Retry a failed render automatically | Cannot repair a broken environment, and hides the real failure |

## 2. Implemented layout

```text
.codex-plugin/plugin.json
skills/codex-maya-*/
scripts/maya_runner.py
scripts/maya_bridge.py
scripts/media_probe.py
schemas/
tests/
```

| Path | Responsibility |
|---|---|
| `scripts/maya_runner.py` | Maya and `mayapy` discovery, ABI validation, argv invocation with an environment allowlist |
| `scripts/maya_bridge.py` | Scene inspection, Playblast, snapshot and restore, receipt construction |
| `scripts/maya_diagnostics.py` | Typed, path-safe environment diagnostics |
| `scripts/media_probe.py` | In-process MP4 container and codec validation |
| Vendored Python source | The official bridge and Playblast modules, checksummed verbatim |

## 3. Key mechanics

- Discover `maya`, `mayapy`, version, Python ABI, and module paths.
- Start with a read-only scene receipt.
- Snapshot selection, current time, playback range, active model panel, camera, display mode, and output settings.
- Generate white-model or material-aware Playblast into a temporary directory.
- Convert only through an already available approved media tool.
- Restore state and atomically publish the validated result.

The restore step is verified rather than assumed: every snapshotted field is compared before and after the operation, and a mismatch raises `RESTORE_UNCONFIRMED` instead of reporting success.

## 4. Configuration and state

| Setting | Location | Notes |
|---|---|---|
| Maya installation | `MAYA_LOCATION` environment variable | Used when `mayapy` is not on `PATH` |
| Maya Python version | `MAYA_PYTHON_VERSION` environment variable | Read during ABI validation |
| Environment allowlist | Enforced by the runner | Only approved variables reach the child process |
| Persistent state | None | Sessions live inside the `mayapy` subprocess |

## 5. Error model

`MAYA_NOT_FOUND`, `ABI_MISMATCH`, `MODULE_LOAD_FAILED`, `MAYA_PROBE_FAILED`, `SCENE_NOT_AUTHORIZED`, `CAMERA_NOT_FOUND`, `PLAYBLAST_FAILED`, `TIMEOUT`, `RESTORE_UNCONFIRMED`, `MEDIA_INVALID`, `DIAGNOSTICS_FAILED`, `PATH_INVALID`, `PYTHON_NOT_FOUND`, `UPLOAD_NOT_AUTHORIZED`.

Discovery and diagnostic failures come from `scripts/maya_runner.py` and `scripts/maya_diagnostics.py`; scene and media failures come from `scripts/maya_bridge.py` and `scripts/media_probe.py`. Each code names the failed precondition, so a caller never has to parse a message.

## 6. Test strategy

Use fake `maya.cmds` for unit TDD, fixture scripts for batch behavior, path tests including Unicode locations, and separately authorized real-Maya smoke tests. A module-import success alone is not runtime acceptance.

| Layer | Proves | Command |
|---|---|---|
| Unit | Discovery, bridge mechanics, restore comparison, receipt shape | `python3 -m unittest discover -s tests -v` |
| Fixture | Batch inspection and Playblast behavior against fake Maya APIs | same suite, fixture classes |
| Path | Unicode and unusual project locations | same suite, path classes |
| Distribution | Manifests, references, and required files | `python3 scripts/validate_distribution.py` |
| Real Maya | Live discovery, capture, and browser hand-off | Separate authorized gate, recorded in `docs/verification/maya-runtime.md` |

## 7. Compatibility

| Aspect | Position |
|---|---|
| Python | 3.7 or newer, matching the Maya interpreter |
| Maya | 2022 or newer |
| Out of scope | Maya before 2022, and a Linux install with no explicit `MAYA_LOCATION` |
| Verification rule | Every supported OS/Maya/Python combination needs its own recorded runtime test |

## 8. Evidence map

| Claim | Evidence |
|---|---|
| Discovery and ABI validation | `scripts/maya_runner.py` |
| Restore verification | `scripts/maya_bridge.py` |
| Media validation | `scripts/media_probe.py` |
| Offline scope and gaps | `docs/verification/offline.md` |
| Runtime status | `docs/verification/maya-runtime.md` |
