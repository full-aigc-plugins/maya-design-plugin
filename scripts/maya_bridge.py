"""Read-only Maya scene inspection.

The bridge never mutates Maya state. It returns a single JSON-ready dict that
matches `schemas/scene_receipt.schema.json`. The receipt is byte-stable so two
inspections of the same scene produce the same JSON (modulo a fresh UUID).

Path handling: the bridge accepts an authorized scene path and redacts its
absolute form from diagnostic output; the scene_path written into the receipt
is the path the caller passed in (it is their responsibility to supply a path
relative to an authorized project root).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

PLUGIN_ID = "codex-maya"
SCHEMA_VERSION = "1.0.0"
DISPLAY_MODES = frozenset({"white_model", "material_preview", "existing_video"})


class SceneNotAuthorizedError(Exception):
    code = "SCENE_NOT_AUTHORIZED"


def _redact(value: str) -> str:
    """Replace absolute paths with a token so diagnostics never leak them."""

    if not value:
        return value
    return "<redacted-path>" if os.path.isabs(value) else value


def _hash_scene_path(scene: Path) -> str:
    """Stable digest of the authorized scene path; used to seed the scene UUID."""

    h = hashlib.sha256()
    h.update(str(scene).encode("utf-8", errors="replace"))
    return h.hexdigest()


def _uuid_from_digest(digest: str) -> str:
    """Derive a deterministic UUID v4-shaped string from a sha256 digest."""

    raw = bytes.fromhex(digest)
    # Force version 4 and the variant nibbles so the result matches the schema's
    # UUID v4 pattern deterministically.
    raw = bytearray(raw)
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    hexed = raw.hex()
    return (
        f"{hexed[0:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:32]}"
    )


def _normalized_display_mode(value: Any) -> str:
    if value not in DISPLAY_MODES:
        raise SceneNotAuthorizedError(
            f"display_mode {value!r} not in {sorted(DISPLAY_MODES)}"
        )
    return value


def _resolve_scene_id(approved_scene: Path) -> str:
    digest = _hash_scene_path(approved_scene)
    return _uuid_from_digest(digest)


def inspect_scene(cmds: Any, approved_scene: Path) -> dict:
    """Return a JSON-ready scene receipt describing the authorized scene.

    The function never mutates Maya state. The caller is responsible for the
    `cmds` argument being the live `maya.cmds` module (or a hermetic fake for
    tests). Two calls with identical inputs return identical receipts modulo
    any caller-provided fields; the `scene_id` is deterministic.
    """

    if approved_scene is None:
        raise SceneNotAuthorizedError("approved_scene is required")

    # Capture selection and current time *before* inspection so we can verify
    # the bridge never mutates them.
    selection_before = tuple(cmds.ls_sl())
    current_time_before = cmds.currentTime()
    loaded_before = tuple(p for p in getattr(cmds, "loaded_plugins", ()))

    cameras = tuple(cmds.listCameras())
    if not cameras:
        raise SceneNotAuthorizedError("no cameras found in scene")

    approved_camera = cameras[0]  # bridge uses the first camera deterministically

    pr = cmds.playbackRange()
    frame_range = {
        "start": int(pr[0]),
        "end": int(pr[1]),
        "current": int(current_time_before),
    }
    if frame_range["start"] > frame_range["end"]:
        # Bridge-level rule; schema only enforces non-negative integers.
        raise SceneNotAuthorizedError(
            f"inverted playback range: start={frame_range['start']} > end={frame_range['end']}"
        )

    width = int(cmds.getAttr("defaultResolution.resolutionWidth"))
    height = int(cmds.getAttr("defaultResolution.resolutionHeight"))
    resolution = {"width": width, "height": height}

    model_panels = tuple(cmds.getPanel("-type", "modelPanel"))
    if not model_panels:
        display_mode = "material_preview"  # safe default; no panel means nothing to override
    else:
        mode_value = str(cmds.getAttr(f"{model_panels[0]}.displayMode"))
        display_mode = _normalized_display_mode(_translate_panel_mode(mode_value))

    materials = tuple(cmds.ls("materials"))
    references = tuple(cmds.ls("references"))
    namespaces = tuple(cmds.ls("namespaces"))
    callbacks = tuple(cmds.ls("callbacks"))
    unknown_plugins = tuple(cmds.ls(type="unknownPlugin"))

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": PLUGIN_ID,
        "scene_id": _resolve_scene_id(approved_scene),
        "scene_path": str(approved_scene),
        "approved_camera": approved_camera,
        "frame_range": frame_range,
        "resolution": resolution,
        "display_mode": display_mode,
        "materials": list(materials),
        "references": list(references),
        "namespaces": list(namespaces),
        "callbacks": list(callbacks),
        "unknown_plugins": list(unknown_plugins),
        "inspection_status": "ok" if not unknown_plugins else "degraded",
    }

    # Re-check state to prove no mutation.
    selection_after = tuple(cmds.ls_sl())
    current_time_after = cmds.currentTime()
    if selection_after != selection_before:
        raise RuntimeError("inspection mutated selection")
    if current_time_after != current_time_before:
        raise RuntimeError("inspection mutated current time")
    loaded_after = tuple(p for p in getattr(cmds, "loaded_plugins", ()))
    if loaded_after != loaded_before:
        raise RuntimeError("inspection loaded new plugins")

    return receipt


def _translate_panel_mode(value: str) -> str:
    """Map a Maya model panel display mode to the receipt enum."""

    if value in ("wireframe",):
        return "white_model"
    return "material_preview"


def to_json(receipt: Mapping[str, Any]) -> str:
    """Return the canonical, byte-stable JSON form of a receipt.

    Tests use this to assert determinism across runs.
    """

    return json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def diagnostics_for(receipt: Mapping[str, Any]) -> dict:
    """Return a diagnostic view of a receipt with absolute paths redacted."""

    view: dict[str, Any] = {}
    for key, value in receipt.items():
        if isinstance(value, str):
            view[key] = _redact(value)
        elif isinstance(value, list):
            view[key] = [_redact(item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, dict):
            view[key] = {k: (_redact(v) if isinstance(v, str) else v) for k, v in value.items()}
        else:
            view[key] = value
    return view


__all__ = [
    "DISPLAY_MODES",
    "PLUGIN_ID",
    "SCHEMA_VERSION",
    "SceneNotAuthorizedError",
    "diagnostics_for",
    "inspect_scene",
    "to_json",
]


if __name__ == "__main__":  # pragma: no cover - exercised via tests and Skills
    import argparse

    parser = argparse.ArgumentParser(description="Inspect an authorized Maya scene")
    parser.add_argument("scene", type=Path)
    parser.add_argument("--bridge-script", type=Path, default=None)
    args = parser.parse_args()
    # Real Maya invocation is owned by Skills; this entrypoint exists only for
    # CLI discoverability.
    print(json.dumps({"hint": "use the Skills; this CLI is intentionally a stub"}))
    sys.exit(0)
