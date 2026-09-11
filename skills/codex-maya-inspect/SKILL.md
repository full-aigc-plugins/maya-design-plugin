---
name: codex-maya-inspect
description: |
  Read-only inspection of an authorized Maya scene. Produces a Codex scene
  receipt describing cameras, playback range, current time, resolution,
  active model panel, display mode, materials, references, namespaces,
  callbacks, and unknown plug-ins. Use when the user wants to know what a
  scene contains before exporting, rendering, or sharing it. NEVER mutates
  the scene and never loads plug-ins; if the user asks for export or
  Playblast, use `codex-maya-export-preview` instead.
---

# codex-maya-inspect

## Inputs

- `scene_id` — Codex UUID assigned to the scene (the Skill auto-generates one
  if the caller passes a path).
- `scene_path` — relative path from the authorized project root.

## Outputs

A `scene_receipt` (JSON) conforming to
`schemas/scene_receipt.schema.json`:

```json
{
  "schema_version": "1.0.0",
  "plugin_id": "codex-maya",
  "scene_id": "<uuid>",
  "scene_path": "scenes/hero.ma",
  "approved_camera": "camera1",
  "frame_range": {"start": 1, "end": 240, "current": 12},
  "resolution": {"width": 1920, "height": 1080},
  "display_mode": "material_preview",
  "materials": ["lambert1"],
  "references": ["ref1.ma"],
  "namespaces": ["ns1"],
  "callbacks": ["frame_change"],
  "unknown_plugins": [],
  "inspection_status": "ok"
}
```

## Implementation

1. Discover Maya via `scripts/maya_runner.py::discover_maya`.
2. Drive `mayapy` with `scripts/maya_bridge.py::inspect_scene`.
3. Emit the receipt to stdout; never write the receipt to disk unless the
   caller explicitly asks for `output_path`.

## Safety

- No plug-in loading. The Skill rejects `maya.cmds.loadPlugin` at runtime.
- No selection mutation. The Skill rejects `maya.cmds.select` at runtime.
- No `currentTime` writes. The Skill rejects `maya.cmds.currentTime(edit=True)`
  at runtime.
- Absolute paths are redacted in any diagnostic string returned to the agent.

## Errors

- `SCENE_NOT_AUTHORIZED` — the scene path is not authorized, no cameras exist,
  or the playback range is inverted.
- `MAYA_NOT_FOUND` — Maya/mayapy is not installed.
- `ABI_MISMATCH` — installed Maya has an unsupported Python ABI.
- `MODULE_LOAD_FAILED` — required Maya modules are missing.
