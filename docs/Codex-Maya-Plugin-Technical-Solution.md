# Codex Maya Plugin Technical Solution

> Design-stage proposal, 2026-09-11.

## Decision

Use a Codex Skill layer, an argv-only runner, and a Maya Python bridge supporting batch inspection and controlled Playblast. Do not copy the official Dreamina Maya uploader.

## Planned layout

```text
.codex-plugin/plugin.json
skills/codex-maya-*/
scripts/maya_runner.py
scripts/maya_bridge.py
scripts/media_probe.py
schemas/
tests/
```

## Key mechanics

- Discover `maya`, `mayapy`, version, Python ABI, and module paths.
- Start with a read-only scene receipt.
- Snapshot selection, current time, playback range, active model panel, camera, display mode, and output settings.
- Generate white-model or material-aware Playblast into a temporary directory.
- Convert only through an already available approved media tool.
- Restore state and atomically publish the validated result.

## Error model

`MAYA_NOT_FOUND`, `ABI_MISMATCH`, `MODULE_LOAD_FAILED`, `SCENE_NOT_AUTHORIZED`, `CAMERA_NOT_FOUND`, `PLAYBLAST_FAILED`, `TIMEOUT`, `RESTORE_UNCONFIRMED`, `MEDIA_INVALID`.

## Test strategy

Use fake `maya.cmds` for unit TDD, fixture scripts for batch behavior, path tests including Unicode locations, and separately authorized real-Maya smoke tests. A module-import success alone is not runtime acceptance.
