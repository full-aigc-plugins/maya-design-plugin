#!/usr/bin/env python3
"""Receipt adapter consumed by codex-dreamina-3d after local preview validation.

`maya-design`'s own receipt (`schemas/artifact_receipt.schema.json`) is the
plugin's internal record. `codex-dreamina-3d` does not consume that shape: it
validates an incoming preview receipt with `scripts/handoff_validator.py`, which
requires `producer_plugin` / `producer_version` / `path` / `sha256` / `codec` /
`container` / `dimensions` / `fps` / `bytes` / `camera` / `frame_range` /
`preview_mode` / `restoration`.

This module is the single translation point. It derives the consumer's shape
from a produced artifact plus a media probe, and it **refuses** to emit a
receipt the consumer would reject rather than pushing that failure downstream
where the message is worse.

Mirrors `codex-blender-plugin/scripts/dreamina_adapter.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Mapping

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import maya_runner  # noqa: E402  - after sys.path injection
import media_probe  # noqa: E402

PRODUCER_PLUGIN = "maya-design"
PRODUCER_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "1.0.0"

# Ranges enforced by codex-dreamina-3d's handoff_validator. Kept here so an
# out-of-range artifact fails at the producer with a precise message instead of
# arriving at the consumer as an opaque rejection.
SUPPORTED_CODEC = "h264"
SUPPORTED_CONTAINER = "mp4"
MIN_DIMENSION = 16
MAX_DIMENSION = 4096
MIN_FPS = 1.0
MAX_FPS = 120.0
MAX_DURATION_SECONDS = 60.0
PREVIEW_MODES = ("camera_render", "local_video")

# maya-design's own display_mode -> the consumer's preview_mode.
_DISPLAY_TO_PREVIEW = {
    "white_model": "camera_render",
    "material_preview": "camera_render",
    "existing_video": "local_video",
}

# media_probe reports the ISO BMFF sample-entry FourCC; the consumer wants the
# codec family name.
_CODEC_ALIASES = {"avc1": "h264", "avc": "h264", "h264": "h264"}


class AdapterError(RuntimeError):
    """Raised when the artifact cannot be expressed as a valid handoff receipt."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AdapterError(message)


def _positive_int(value: object, label: str) -> int:
    _require(isinstance(value, (int, float)), f"{label} must be numeric (got {value!r})")
    number = int(value)
    _require(number > 0, f"{label} must be positive (got {number})")
    return number


def build_preview_receipt(
    *,
    artifact_id: str,
    media_path: Path,
    media: Mapping[str, object],
    sha256: str,
    fps: float,
    camera_name: str,
    frame_range: Mapping[str, object],
    preview_mode: str,
    restoration_evidence: str = "Maya scene state restored and verified by the Codex driver",
) -> dict:
    """Translate a produced artifact into the codex-dreamina-3d receipt shape.

    ``fps`` is passed in rather than read from ``media``: media_probe reports the
    ISO BMFF *media timescale* (24000 for 24 fps), which is not a frame rate and
    would be rejected by the consumer's 1..120 range. The export request is the
    authoritative statement of the frame rate that was rendered.

    Every value is range-checked against the consumer's limits first. An
    artifact that cannot satisfy them raises :class:`AdapterError` here.
    """

    _require(isinstance(artifact_id, str) and artifact_id, "artifact_id must be a non-empty string")
    _require(preview_mode in PREVIEW_MODES,
             f"preview_mode must be one of {PREVIEW_MODES} (got {preview_mode!r})")

    codec_raw = str(media.get("codec") or "").lower()
    codec = _CODEC_ALIASES.get(codec_raw)
    _require(codec == SUPPORTED_CODEC,
             f"artifact codec must be h264, got {codec_raw!r}")

    container = str(media.get("container") or "").lower()
    _require(container == SUPPORTED_CONTAINER,
             f"artifact container must be mp4, got {container!r}")

    width = _positive_int(media.get("width"), "width")
    height = _positive_int(media.get("height"), "height")
    _require(MIN_DIMENSION <= width <= MAX_DIMENSION,
             f"width {width} outside [{MIN_DIMENSION}, {MAX_DIMENSION}]")
    _require(MIN_DIMENSION <= height <= MAX_DIMENSION,
             f"height {height} outside [{MIN_DIMENSION}, {MAX_DIMENSION}]")

    fps_value = float(fps or 0)
    _require(MIN_FPS <= fps_value <= MAX_FPS,
             f"fps {fps_value} outside [{MIN_FPS}, {MAX_FPS}]")

    duration = float(media.get("duration_seconds") or 0)
    _require(0 < duration <= MAX_DURATION_SECONDS,
             f"duration {duration}s outside (0, {MAX_DURATION_SECONDS}]")

    size_bytes = _positive_int(media.get("file_size_bytes"), "file_size_bytes")

    _require(isinstance(camera_name, str) and camera_name,
             "camera_name must be a non-empty string")

    start = frame_range.get("start")
    end = frame_range.get("end")
    _require(isinstance(start, int) and isinstance(end, int),
             "frame_range.start/end must be integers")
    _require(0 <= start <= end,
             f"frame_range needs 0 <= start <= end (got {start}..{end})")

    _require(isinstance(sha256, str) and len(sha256) == 64
             and all(c in "0123456789abcdef" for c in sha256.lower()),
             "sha256 must be 64 lowercase hex characters")

    return {
        "schema_version": SCHEMA_VERSION,
        "producer_plugin": PRODUCER_PLUGIN,
        "producer_version": PRODUCER_VERSION,
        "artifact_id": artifact_id,
        "path": str(media_path),
        "sha256": sha256.lower(),
        "codec": SUPPORTED_CODEC,
        "container": SUPPORTED_CONTAINER,
        "dimensions": {"width": width, "height": height},
        "fps": fps_value,
        "duration_seconds": duration,
        "bytes": size_bytes,
        "camera": {"name": camera_name},
        "frame_range": {"start": start, "end": end},
        "preview_mode": preview_mode,
        # The consumer requires exactly "confirmed". maya-design only reaches
        # this point when the driver's outer verification pass found no drift
        # (otherwise RESTORE_UNCONFIRMED was raised and we never got here).
        "restoration": {"status": "confirmed", "evidence": restoration_evidence},
    }


def receipt_from_maya_result(result: Mapping[str, object], *, media_path: Path,
                            camera_name: str, frame_range: Mapping[str, object],
                            fps: float) -> dict:
    """Build the handoff receipt from a `run_jimeng_flow` / `export_playblast` result."""

    artifact = result.get("artifact_receipt") if isinstance(result, dict) else None
    if not isinstance(artifact, dict):
        artifact = result if isinstance(result, dict) else {}

    display_mode = str(artifact.get("display_mode") or "white_model")
    preview_mode = _DISPLAY_TO_PREVIEW.get(display_mode)
    if preview_mode is None:
        raise AdapterError(f"unknown display_mode {display_mode!r}")

    media = media_probe.probe(media_path)
    return build_preview_receipt(
        artifact_id=str(artifact.get("artifact_id") or uuid.uuid4()),
        media_path=media_path,
        media=media,
        sha256=media_probe.sha256(media_path),
        fps=fps,
        camera_name=camera_name,
        frame_range=frame_range,
        preview_mode=preview_mode,
    )


def run_inspect(request: Mapping[str, object], *, explicit_root: str | None,
                timeout: float) -> dict:
    runtime = maya_runner.discover_maya(explicit_root, "")
    details = maya_runner.run_request(
        runtime,
        {"action": "inspect", "scene_path": request.get("scene")},
        timeout=timeout,
    )
    return {"status": "ready", "scene": request.get("scene"), "details": details}


def run_export(request: Mapping[str, object], *, output: Path, explicit_root: str | None,
               timeout: float, authorize_upload: bool) -> dict:
    runtime = maya_runner.discover_maya(explicit_root, "")
    frame_range = request.get("frame_range") or {}
    camera_name = str(request.get("camera_name") or "")

    payload = {
        "action": "jimeng_flow" if authorize_upload else "export",
        "request": {
            "mode": request.get("mode") or "white_model",
            "camera": camera_name,
            "start_frame": int(frame_range.get("start", 0)),
            "end_frame": int(frame_range.get("end", 0)),
            "frame_rate": float(request.get("fps") or 24),
            "width": int(request.get("width") or 1920),
            "height": int(request.get("height") or 1080),
            "scene_id": request.get("scene_id"),
            "authorize_upload": bool(authorize_upload),
            "output_dir": str(output.parent) if output.parent else None,
        },
    }
    result = maya_runner.run_request(runtime, payload, timeout=timeout)
    return receipt_from_maya_result(
        result,
        media_path=output,
        camera_name=camera_name,
        frame_range={"start": int(frame_range.get("start", 0)),
                     "end": int(frame_range.get("end", 0))},
        fps=float(request.get("fps") or 24),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="codex-dreamina-3d preview adapter for maya-design"
    )
    parser.add_argument("--request")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output")
    parser.add_argument("--explicit-root", default=None)
    parser.add_argument("--timeout", type=float, default=maya_runner.DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--authorize-upload", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)

    receipt_path = Path(args.receipt)
    try:
        # Mirror codex-blender's adapter: a bare receipt path means "is a
        # previous run's receipt present?".
        if args.status:
            if receipt_path.is_file():
                return 0
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps({"status": "unknown"}), encoding="utf-8")
            return 2

        if not args.request:
            raise AdapterError("--request is required")

        request = json.loads(Path(args.request).read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise AdapterError("request must be a JSON object")

        if args.inspect:
            receipt = run_inspect(request, explicit_root=args.explicit_root, timeout=args.timeout)
        else:
            if not args.output:
                raise AdapterError("--output is required for preview export")
            receipt = run_export(
                request,
                output=Path(args.output),
                explicit_root=args.explicit_root,
                timeout=args.timeout,
                authorize_upload=args.authorize_upload,
            )

        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        return 0
    except Exception as exc:  # noqa: BLE001 - the consumer reads the receipt file
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps({"status": "failed", "error": str(exc)}), encoding="utf-8"
        )
        sys.stderr.write(str(exc) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
