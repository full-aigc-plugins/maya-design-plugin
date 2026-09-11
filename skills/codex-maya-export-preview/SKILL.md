---
name: codex-maya-export-preview
description: |
  Reversible Playblast export from an authorized Maya scene. Produces a Codex
  artifact receipt (codec, fps, dimensions, SHA-256, duration, size,
  restoration status) for either a fresh Maya `playblast` (white-model or
  material-preview) or an existing local video file. Every temporary Maya
  state change (selection, current time, playback range, camera, active
  panel, displayAppearance, displayTextures, renderer, image format,
  resolution, shader overrides) is captured and restored in `finally`,
  even on exception, cancellation, or timeout. NEVER auto-retries the
  Playblast on failure. NEVER installs packages. Use this Skill for any
  "export preview", "Playblast", "render preview" request. For pure scene
  inspection use `codex-maya-inspect`; for diagnostic questions use
  `codex-maya-diagnose`.
---

# codex-maya-export-preview

## Modes

- `white_model` — render a clean white-model Playblast from the selected
  camera.
- `material_preview` — render with the scene's user materials and textures
  when present; fall back to white-model otherwise.
- `existing_video` — skip Maya entirely; produce a receipt from a local
  `.mp4`/`.mov`/`.webm`/`.avi` chosen by the user.

## Inputs

- `mode` — `white_model` / `material_preview` / `existing_video`
- `camera` — Maya camera name; auto-selected if omitted.
- `start_frame`, `end_frame` — inclusive frame range.
- `width`, `height`, `frame_rate` — output parameters.
- `scene_path` — authorized scene path (required for white-model / material-preview).
- `video_path` — local video (required for existing-video mode).
- `output_dir` — optional override for the temporary output directory.

## Outputs

A Codex `artifact_receipt` (JSON) conforming to
`schemas/artifact_receipt.schema.json`:

```json
{
  "schema_version": "1.0.0",
  "plugin_id": "codex-maya",
  "artifact_id": "<uuid>",
  "scene_id": "<uuid>",
  "media_path": "previews/hero.mp4",
  "media_format": "video/mp4",
  "media_sha256": "<64 hex>",
  "duration_seconds": 10.0,
  "frame_rate": 24.0,
  "width": 1920,
  "height": 1080,
  "file_size_bytes": 1024,
  "restoration_status": "restored",
  "display_mode": "white_model"
}
```

## Implementation

1. Discover Maya via `scripts/maya_runner.py::discover_maya`.
2. Drive `mayapy` with `scripts/maya_bridge.py::export_playblast`. The
   bridge wraps the vendored Jimeng/Dreamina Maya uploader
   (`scripts/jimeng_third_party/`) inside `restored_maya_state`.
3. Validate the produced media with `scripts/media_probe.py::validate_receipt`.
4. The Jimeng local-bridge response (`redirect_url`, `resource_info_url`,
   `expires_at`) is captured in a process-local session log and is NEVER
   included in the receipt. The calling Skill can open the link for the
   user from the session log.

## Safety

- Reversible: snapshot/restore on every Maya state value touched by the
  export path. Restoration failures raise `RESTORE_UNCONFIRMED`.
- One-shot: never retries a failed Playblast automatically. The user must
  re-invoke.
- No installs: rejects missing codecs or Python packages; the user must
  install them explicitly outside the Codex pipeline.
- Vendor integrity: `scripts/jimeng_third_party/` is checksum-locked; any
  accidental edit fails the suite.

## Errors

- `MAYA_NOT_FOUND` / `ABI_MISMATCH` / `MODULE_LOAD_FAILED` — discovery failed.
- `CAMERA_NOT_FOUND` — requested camera is not present in the scene.
- `PLAYBLAST_FAILED` — capture, conversion, validation, or publication step
  failed inside `restored_maya_state`.
- `RESTORE_UNCONFIRMED` — Maya state did not return to the pre-export snapshot.
- `MEDIA_INVALID` — produced media failed `media_probe.validate_receipt`.
- `SCENE_NOT_AUTHORIZED` — mode is `existing_video` but the local file is
  missing or unsupported.
