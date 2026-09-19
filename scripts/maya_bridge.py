"""Read-only Maya scene inspection and reversible Playblast export.

The bridge never mutates Maya state except inside the explicitly bounded
`restored_maya_state` context manager, which snapshots and restores every
observable value the bridge touches. Receipts are JSON-ready and byte-stable.

Playblast integration: the bridge imports the vendored Jimeng/Dreamina Maya
uploader (`scripts/jimeng_third_party/jimeng_maya_uploader/`) and wraps its
`playblast.run_playblast` and `upload_bridge.start_local_bridge` inside
`restored_maya_state`. The Jimeng `redirect_url` / `resource_info_url` never
appear in the Codex artifact receipt (see Ruling 2 in the SDD ledger).

Path handling: the bridge accepts an authorized scene path and redacts its
absolute form from diagnostic output; the scene_path written into the receipt
is the path the caller passed in (it is their responsibility to supply a path
relative to an authorized project root).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Iterator, Mapping

PLUGIN_ID = "maya-design"
SCHEMA_VERSION = "1.0.0"
DISPLAY_MODES = frozenset({"white_model", "material_preview", "existing_video"})
JIMENG_VENDOR_DIR = Path(__file__).resolve().parent / "jimeng_third_party" / "jimeng_maya_uploader"
JIMENG_VENDOR_CHECKSUM = (
    "33dc6dfb766dc43a515c91547ab58c26d044079296b92f5c4689b9eb5106191f"
)
_BRIDGE_SESSION_KEY = "_maya_design_bridge_sessions"


class SceneNotAuthorizedError(Exception):
    code = "SCENE_NOT_AUTHORIZED"


class CameraNotFoundError(Exception):
    code = "CAMERA_NOT_FOUND"


class PlayblastFailedError(Exception):
    code = "PLAYBLAST_FAILED"


class TimeoutError_(Exception):
    code = "TIMEOUT"


class RestoreUnconfirmedError(Exception):
    code = "RESTORE_UNCONFIRMED"


class UploadNotAuthorizedError(Exception):
    code = "UPLOAD_NOT_AUTHORIZED"


TimeoutError = TimeoutError_  # alias for callers


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


# ---------------------------------------------------------------------------
# Playblast surface — reversible wrapper around the vendored Jimeng uploader.
# ---------------------------------------------------------------------------


# Scene-level state the Codex layer owns. Restoration is deliberately layered:
#
#   restored_maya_state (this module)      -- scene-level: renderer, image format,
#     └─ jimeng playblast.run_playblast       resolution, playback range, and a
#          └─ ViewportPreviewState            verification pass over everything
#             (jimeng_third_party)            below.
#                                           -- viewport-level: 29 model-editor
#                                              flags plus selection and current
#                                              time, restored by the vendored
#                                              Jimeng implementation.
#
# The five fields that appear in both layers (selection, current_time, camera,
# display_appearance, display_textures) are covered twice on purpose: the
# inner layer is what actually puts them back, and the outer verification pass
# is what lets `artifact_receipt.restoration_status` claim they were restored.
# Without the outer pass there is no way to detect a silent restore failure.
SNAPSHOT_FIELDS = (
    "selection",
    "current_time",
    "playback_range",
    "camera",
    "active_panel",
    "display_appearance",
    "display_textures",
    "renderer",
    "image_format",
    "resolution",
)


def _read_snapshot(cmds: Any) -> dict:
    """Capture every observable Maya value the Playblast path touches.

    Only scene-level values are captured here; the viewport flags are owned by
    the vendored Jimeng `ViewportPreviewState` (see the note above).
    """

    return {
        "selection": list(cmds.ls(selection=True, long=True) or []),
        "current_time": cmds.currentTime(query=True),
        "playback_range": [
            int(cmds.playbackOptions(query=True, minTime=True)),
            int(cmds.playbackOptions(query=True, maxTime=True)),
        ],
        "camera": _active_camera(cmds),
        "active_panel": _active_panel(cmds),
        "display_appearance": _panel_attribute(cmds, "displayAppearance"),
        "display_textures": _panel_attribute(cmds, "displayTextures"),
        "renderer": _renderer(cmds),
        "image_format": _image_format(cmds),
        "resolution": [
            int(cmds.getAttr("defaultResolution.width")),
            int(cmds.getAttr("defaultResolution.height")),
        ],
    }


def _active_camera(cmds: Any) -> str | None:
    panel = _active_panel(cmds)
    if panel:
        try:
            return cmds.modelPanel(panel, query=True, camera=True)
        except Exception:
            pass
    cameras = cmds.ls(type="camera", long=True) or []
    if cameras:
        parent = cmds.listRelatives(cameras[0], parent=True, fullPath=True) or []
        return parent[0] if parent else cameras[0]
    return None


def _active_panel(cmds: Any) -> str | None:
    try:
        panel = cmds.getPanel(withFocus=True)
    except Exception:
        panel = None
    if panel:
        try:
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                return panel
        except Exception:
            pass
    panels = cmds.getPanel(type="modelPanel") or []
    return panels[0] if panels else None


def _panel_attribute(cmds: Any, attr: str) -> dict:
    panel = _active_panel(cmds)
    out: dict = {}
    if not panel:
        return out
    try:
        out[panel] = cmds.modelPanel(panel, query=True, **{attr: True})
    except Exception:
        pass
    return out


def _renderer(cmds: Any) -> str:
    try:
        return cmds.getAttr("defaultRenderGlobals.currentRenderer")
    except Exception:
        return "vp2"


def _image_format(cmds: Any) -> str:
    try:
        return cmds.getAttr("defaultRenderGlobals.imageFormat")
    except Exception:
        return "png"


def _restore_snapshot(cmds: Any, snapshot: Mapping[str, Any]) -> None:
    """Restore every field we snapshotted. Failures are logged, not raised."""

    for field_name in SNAPSHOT_FIELDS:
        try:
            _restore_field(cmds, field_name, snapshot.get(field_name))
        except Exception:
            # Restoration must never raise; the finally block in
            # restored_maya_state will check pre/post equality and surface a
            # RESTORE_UNCONFIRMED error to the caller.
            pass


def _restore_field(cmds: Any, name: str, value: Any) -> None:
    if value is None:
        return
    if name == "selection":
        cmds.select(clear=True)
        if value:
            cmds.select(value, replace=True)
    elif name == "current_time":
        cmds.currentTime(int(value), edit=True)
    elif name == "playback_range":
        cmds.playbackOptions(
            edit=True,
            minTime=int(value[0]),
            maxTime=int(value[1]),
        )
    elif name == "camera":
        panel = _active_panel(cmds)
        if panel and value:
            cmds.modelPanel(panel, edit=True, camera=value)
    elif name == "active_panel":
        return  # the active panel is a runtime concept; nothing to restore
    elif name == "display_appearance" and value:
        for panel, mode in value.items():
            cmds.modelPanel(panel, edit=True, displayAppearance=mode)
    elif name == "display_textures" and value:
        for panel, enabled in value.items():
            cmds.modelPanel(panel, edit=True, displayTextures=bool(enabled))
    elif name == "renderer":
        cmds.setAttr("defaultRenderGlobals.currentRenderer", value, type="string")
    elif name == "image_format":
        cmds.setAttr("defaultRenderGlobals.imageFormat", int(value))
    elif name == "resolution":
        cmds.setAttr("defaultResolution.width", int(value[0]))
        cmds.setAttr("defaultResolution.height", int(value[1]))


@contextlib.contextmanager
def restored_maya_state(cmds: Any) -> Iterator[Mapping[str, Any]]:
    """Snapshot every Maya value the bridge touches and restore on exit.

    The yielded mapping is the snapshot taken at entry. The bridge MUST mutate
    only inside the `with` block; any field whose post-exit value differs from
    the snapshot raises :class:`RestoreUnconfirmedError`.
    """

    snapshot = _read_snapshot(cmds)
    try:
        yield snapshot
    finally:
        _restore_snapshot(cmds, snapshot)
        current = _read_snapshot(cmds)
        for field_name in SNAPSHOT_FIELDS:
            if current.get(field_name) != snapshot.get(field_name):
                raise RestoreUnconfirmedError(
                    f"restoration mismatch on field {field_name!r}"
                )


def verify_vendor_checksum() -> None:
    """Raise if the Jimeng subtree has been edited."""

    root = JIMENG_VENDOR_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"Jimeng vendor directory missing: {root}")
    digest = hashlib.sha256()
    for dirpath, _, filenames in os.walk(root):
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(full.read_bytes())
    if digest.hexdigest() != JIMENG_VENDOR_CHECKSUM:
        raise RestoreUnconfirmedError(
            "Jimeng vendor subtree was modified; checksum drift detected."
        )


def _import_jimeng_playblast():
    """Lazy import so tests that fake maya.cmds do not trigger real Maya."""

    if str(JIMENG_VENDOR_DIR.parent) not in sys.path:
        sys.path.insert(0, str(JIMENG_VENDOR_DIR.parent))
    import jimeng_maya_uploader.playblast as playblast  # type: ignore[import-not-found]

    return playblast


def _import_jimeng_upload_bridge():
    if str(JIMENG_VENDOR_DIR.parent) not in sys.path:
        sys.path.insert(0, str(JIMENG_VENDOR_DIR.parent))
    import jimeng_maya_uploader.upload_bridge as upload_bridge  # type: ignore[import-not-found]

    return upload_bridge


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _existing_video_receipt(
    request: Mapping[str, Any], media_path: str | Path | None = None
) -> dict:
    """Build a receipt for the `existing_video` mode — no scene mutation."""

    video_path = Path(str(media_path or request["video_path"]))
    if not video_path.is_file():
        raise SceneNotAuthorizedError(f"video_path not found: {video_path}")
    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": PLUGIN_ID,
        "artifact_id": str(uuid.uuid4()),
        "scene_id": str(request.get("scene_id") or uuid.uuid4()),
        "media_path": str(video_path),
        "media_format": "video/mp4",
        "media_sha256": _sha256_file(video_path),
        "duration_seconds": float(request.get("duration_seconds") or 0.0),
        "frame_rate": float(request.get("frame_rate") or 24.0),
        "width": int(request.get("width") or 0),
        "height": int(request.get("height") or 0),
        "file_size_bytes": int(video_path.stat().st_size),
        "restoration_status": "restored",
        "display_mode": "existing_video",
    }


def _record_bridge_session(bridge_result: Mapping[str, Any]) -> None:
    """Store the full Jimeng bridge response in a process-local log.

    The log lives in `sys.modules[_BRIDGE_SESSION_KEY]` so it is dropped when
    the `mayapy` subprocess exits; nothing about the local-bridge token leaks
    to disk or to the Codex artifact contract.
    """

    sessions = getattr(sys.modules.get(_BRIDGE_SESSION_KEY), "sessions", None)
    if sessions is None:
        sessions = []
        import types

        mod = types.ModuleType(_BRIDGE_SESSION_KEY)
        mod.sessions = sessions
        sys.modules[_BRIDGE_SESSION_KEY] = mod
    sessions.append(dict(bridge_result))


def consume_bridge_session_log() -> list:
    """Return and clear the in-process bridge session log."""

    mod = sys.modules.get(_BRIDGE_SESSION_KEY)
    sessions = list(getattr(mod, "sessions", []) or []) if mod else []
    if mod is not None:
        mod.sessions = []
    return sessions


def _link_result(bridge_response: Mapping[str, Any]) -> dict:
    """Return the ephemeral Jimeng link fields needed by the Codex caller."""

    redirect_url = str(bridge_response.get("redirect_url") or "")
    if bridge_response.get("status") != "ready" or not redirect_url:
        raise PlayblastFailedError("Jimeng local bridge did not return a ready link")
    return {
        "status": "ready",
        "redirect_url": redirect_url,
        "expires_at": bridge_response.get("expires_at"),
        "port": bridge_response.get("port"),
    }


def run_jimeng_flow(cmds: Any, request: Mapping[str, Any]) -> dict:
    """Run an authorized official Jimeng flow and return artifact plus live link.

    The stable artifact receipt remains token-free. The link is returned in a
    separate ephemeral block so Codex can hand it to the user before the Maya
    process and loopback bridge exit.
    """

    if request.get("authorize_upload") is not True:
        raise UploadNotAuthorizedError(
            "explicit authorize_upload=true is required before creating a Jimeng link"
        )

    mode = str(request.get("mode") or "white_model")
    consume_bridge_session_log()

    if mode == "existing_video":
        verify_vendor_checksum()
        upload_bridge = _import_jimeng_upload_bridge()
        try:
            bridge_response = dict(
                upload_bridge.start_local_bridge(
                    video_path=str(request["video_path"]),
                    prompt=str(request.get("prompt") or ""),
                    target_url=str(
                        request.get("target_url")
                        or "https://jimeng.jianying.com/ai-tool/home"
                    ),
                    max_file_size=request.get("max_file_size"),
                )
            )
        except Exception as exc:
            raise PlayblastFailedError(f"local bridge failed: {exc}") from exc
        artifact = _existing_video_receipt(
            request,
            media_path=bridge_response.get("video") or request["video_path"],
        )
    else:
        artifact = export_playblast(cmds, request)
        sessions = consume_bridge_session_log()
        if not sessions:
            raise PlayblastFailedError("Jimeng local bridge result was not available")
        bridge_response = dict(sessions[-1])

    return {
        "artifact_receipt": artifact,
        "jimeng_link": _link_result(bridge_response),
    }


def export_playblast(cmds: Any, request: Mapping[str, Any]) -> dict:
    """Wrap the Jimeng playblast + bridge inside `restored_maya_state`.

    The request dict carries the Codex-side knobs:

    - `mode`: `white_model`, `material_preview`, or `existing_video`
    - `scene_id`: UUID from the prior `inspect_scene` call
    - For existing-video mode: `video_path`, optional `duration_seconds`,
      `frame_rate`, `width`, `height`.

    For playblast modes the bridge delegates to the Jimeng module and returns
    a Codex receipt built from its result. The full Jimeng response (including
    `redirect_url` / `resource_info_url`) is kept in the process-local session
    log so the calling Skill can open the link, but never enters the receipt.
    """

    mode = str(request.get("mode") or "white_model")
    if mode not in DISPLAY_MODES:
        raise SceneNotAuthorizedError(f"unsupported mode {mode!r}")
    if mode == "existing_video":
        return _existing_video_receipt(request)

    verify_vendor_checksum()

    playblast = _import_jimeng_playblast()
    upload_bridge = _import_jimeng_upload_bridge()

    camera = str(request.get("camera") or playblast.active_camera() or "")
    if not camera or not cmds.objExists(camera):
        raise CameraNotFoundError(f"camera {camera!r} not present in scene")

    start_frame = int(request["start_frame"])
    end_frame = int(request["end_frame"])
    width = int(request.get("width") or cmds.getAttr("defaultResolution.width"))
    height = int(request.get("height") or cmds.getAttr("defaultResolution.height"))
    fps = int(request.get("frame_rate") or 24)
    output_dir = request.get("output_dir")

    bridge_response: dict = {}
    with restored_maya_state(cmds):
        try:
            video_path = Path(playblast.run_playblast(
                camera=camera,
                start_frame=start_frame,
                end_frame=end_frame,
                width=width,
                height=height,
                fps=fps,
                output_dir=output_dir,
                convert_to_mp4=True,
            ))
        except Exception as exc:
            raise PlayblastFailedError(f"playblast failed: {exc}") from exc

        if not video_path.is_file():
            raise PlayblastFailedError(f"playblast produced no file at {video_path}")

        try:
            bridge_response = dict(upload_bridge.start_local_bridge(
                video_path=str(video_path),
                prompt=str(request.get("prompt") or ""),
                target_url=str(request.get("target_url") or "https://jimeng.jianying.com/ai-tool/home"),
                max_file_size=request.get("max_file_size"),
            ))
        except Exception as exc:
            raise PlayblastFailedError(f"local bridge failed: {exc}") from exc

    if bridge_response:
        _record_bridge_session(bridge_response)

    duration = float(request.get("duration_seconds") or 0.0)
    if duration <= 0:
        duration = max(0.0, (end_frame - start_frame + 1) / max(fps, 1))

    return {
        "schema_version": SCHEMA_VERSION,
        "plugin_id": PLUGIN_ID,
        "artifact_id": str(uuid.uuid4()),
        "scene_id": str(request.get("scene_id") or uuid.uuid4()),
        "media_path": str(video_path),
        "media_format": "video/mp4",
        "media_sha256": _sha256_file(video_path),
        "duration_seconds": duration,
        "frame_rate": float(fps),
        "width": int(width),
        "height": int(height),
        "file_size_bytes": int(video_path.stat().st_size),
        "restoration_status": "restored",
        "display_mode": mode,
    }


__all__ = [
    "DISPLAY_MODES",
    "JIMENG_VENDOR_CHECKSUM",
    "JIMENG_VENDOR_DIR",
    "PLUGIN_ID",
    "SCHEMA_VERSION",
    "SNAPSHOT_FIELDS",
    "CameraNotFoundError",
    "PlayblastFailedError",
    "RestoreUnconfirmedError",
    "SceneNotAuthorizedError",
    "TimeoutError",
    "UploadNotAuthorizedError",
    "consume_bridge_session_log",
    "diagnostics_for",
    "export_playblast",
    "inspect_scene",
    "run_jimeng_flow",
    "restored_maya_state",
    "to_json",
    "verify_vendor_checksum",
]


if __name__ == "__main__":  # pragma: no cover - exercised via maya_request.py
    # This module is a library: every public function takes a live
    # ``maya.cmds`` as its first argument, so there is nothing useful it can do
    # under a host interpreter. Rather than pretend to work, point the caller
    # at the real entrypoints.
    sys.stderr.write(
        "maya_bridge is a library and must run inside mayapy.\n"
        "\n"
        "Use the host-side driver instead:\n"
        "  python3 scripts/maya_runner.py inspect --scene <path>\n"
        "  python3 scripts/maya_runner.py export  --request <request.json>\n"
        "  python3 scripts/maya_runner.py jimeng-flow --request <request.json>\n"
        "\n"
        "Inside mayapy, scripts/maya_request.py is the entrypoint.\n"
    )
    raise SystemExit(2)
