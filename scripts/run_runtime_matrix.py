#!/usr/bin/env python3
"""Run the Maya runtime matrix and emit the evidence block for the docs.

This is the command that closes the `runtime_matrix` blocker in the plan's
completion gate. It needs a real Maya install and a fixture scene; it does not
work against a fake `maya.cmds`, on purpose -- inferring Playblast support from
a fake is exactly what the plan forbids.

What it records, per run:

  probe      discovery: mayapy path, Maya version, Python ABI, OS, module paths
  inspect    read-only scene receipt, and that the scene was not mutated
  export     white-model Playblast, the artifact receipt, and media validation
  restore    pre/post scene state equality (the reversible guarantee)
  bridge     Jimeng link creation, if authorization was given
  handoff    the receipt as validated by dreamina-3d's own validator

Usage:

    python3 scripts/run_runtime_matrix.py --scene scenes/hero.ma --camera perspShape \\
        --start 1 --end 48 --output-dir /tmp/maya-matrix

    # record the evidence block into the docs file
    python3 scripts/run_runtime_matrix.py --scene ... --write docs/verification/maya-runtime.md
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import maya_runner  # noqa: E402
import media_probe  # noqa: E402


class MatrixError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _environment() -> dict:
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "host_python": platform.python_version(),
    }


def run_matrix(args) -> dict:
    """Execute every matrix step against a real Maya. Raises on the first that fails."""

    evidence: dict = {
        "generated_at": _now(),
        "environment": _environment(),
        "steps": {},
    }

    # --- probe -------------------------------------------------------------
    runtime = maya_runner.discover_maya(args.explicit_root, args.search_path)
    evidence["steps"]["probe"] = {
        "status": "observed",
        "mayapy": str(runtime.mayapy),
        "maya_version": runtime.version,
        "python_version": runtime.python_version,
        "module_path_count": len(runtime.module_paths),
    }

    scene = Path(args.scene)

    # --- inspect -----------------------------------------------------------
    inspected = maya_runner.run_request(
        runtime,
        {"action": "inspect", "scene_path": str(scene)},
        timeout=args.timeout,
    )
    evidence["steps"]["inspect"] = {
        "status": "observed",
        "approved_camera": inspected.get("approved_camera"),
        "resolution": inspected.get("resolution"),
        "display_mode": inspected.get("display_mode"),
        "inspection_status": inspected.get("inspection_status"),
        "unknown_plugins": inspected.get("unknown_plugins"),
        "scene_id": inspected.get("scene_id"),
    }

    # Running inspect twice must produce byte-identical receipts.
    again = maya_runner.run_request(
        runtime,
        {"action": "inspect", "scene_path": str(scene)},
        timeout=args.timeout,
    )
    evidence["steps"]["inspect"]["deterministic"] = json.dumps(
        inspected, sort_keys=True
    ) == json.dumps(again, sort_keys=True)

    # --- export ------------------------------------------------------------
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    camera = args.camera or inspected.get("approved_camera")
    frame_range = {
        "start": int(args.start),
        "end": int(args.end),
    }

    payload = {
        "action": "export",
        "request": {
            "mode": args.mode,
            "camera": camera,
            "start_frame": frame_range["start"],
            "end_frame": frame_range["end"],
            "frame_rate": float(args.fps),
            "width": int(args.width),
            "height": int(args.height),
            "scene_id": inspected.get("scene_id"),
            "output_dir": str(output_dir),
        },
    }
    exported = maya_runner.run_request(runtime, payload, timeout=args.timeout)
    artifact = exported.get("artifact_receipt") or exported

    media_path = Path(str(artifact.get("media_path")))
    if not media_path.is_file():
        raise MatrixError(f"export reported {media_path} but it does not exist")

    media = media_probe.probe(media_path)
    digests = media_probe.validate_receipt(
        {"media_path": str(media_path), "media_sha256": artifact.get("media_sha256")}
    )
    evidence["steps"]["export"] = {
        "status": "observed",
        "mode": args.mode,
        "camera": camera,
        "frame_range": frame_range,
        "media_path": str(media_path),
        "codec": media["codec"],
        "container": media["container"],
        "dimensions": {"width": media["width"], "height": media["height"]},
        "duration_seconds": media["duration_seconds"],
        "file_size_bytes": media["file_size_bytes"],
        "sha256": digests["media_sha256"],
        "restoration_status": artifact.get("restoration_status"),
    }

    # --- restoration -------------------------------------------------------
    # The driver raises RESTORE_UNCONFIRMED from inside Maya when the outer
    # verification pass sees drift, so reaching here already means the export
    # path reported a clean restore. Re-probe the scene to confirm the
    # *observable* state matches the pre-export receipt.
    after = maya_runner.run_request(
        runtime,
        {"action": "inspect", "scene_path": str(scene)},
        timeout=args.timeout,
    )
    evidence["steps"]["restore"] = {
        "status": "observed",
        "camera_unchanged": after.get("approved_camera") == inspected.get("approved_camera"),
        "frame_range_unchanged": after.get("frame_range") == inspected.get("frame_range"),
        "resolution_unchanged": after.get("resolution") == inspected.get("resolution"),
        "scene_id_unchanged": after.get("scene_id") == inspected.get("scene_id"),
        "driver_reported": artifact.get("restoration_status"),
    }

    # --- bridge (optional) --------------------------------------------------
    if args.authorize_upload:
        flow_payload = dict(payload)
        flow_payload["action"] = "jimeng_flow"
        flow_payload["request"] = dict(payload["request"], authorize_upload=True)
        flow = maya_runner.run_request(runtime, flow_payload, timeout=args.timeout)
        link = flow.get("jimeng_link") or {}
        evidence["steps"]["bridge"] = {
            "status": "observed",
            "link_present": bool(link.get("redirect_url")),
            "expires_at": link.get("expires_at"),
            # Deliberately not recording redirect_url: it carries a live token.
        }
    else:
        evidence["steps"]["bridge"] = {
            "status": "not_authorized",
            "note": "re-run with --authorize-upload to exercise the Jimeng link",
        }

    # --- handoff ------------------------------------------------------------
    handoff_dir = Path(__file__).resolve().parents[1].parent / "dreamina-3d-plugin" / "scripts"
    if handoff_dir.is_dir():
        if str(handoff_dir) not in sys.path:
            sys.path.insert(0, str(handoff_dir))
        import handoff_validator  # type: ignore[import-not-found]

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import dreamina_adapter  # type: ignore[import-not-found]

        receipt = dreamina_adapter.receipt_from_maya_result(
            exported,
            media_path=media_path,
            camera_name=str(camera),
            frame_range=frame_range,
            fps=float(args.fps),
        )
        errors = handoff_validator.validate_artifact(receipt, media_path)
        evidence["steps"]["handoff"] = {
            "status": "observed" if not errors else "failed",
            "validator": "dreamina-3d/scripts/handoff_validator.py",
            "errors": errors,
        }
        if errors:
            raise MatrixError(f"dreamina-3d rejected the receipt: {errors}")
    else:
        evidence["steps"]["handoff"] = {
            "status": "skipped",
            "note": f"dreamina-3d not checked out at {handoff_dir}",
        }

    return evidence


def render_markdown(evidence: dict) -> str:
    env = evidence["environment"]
    steps = evidence["steps"]
    probe = steps["probe"]
    inspect = steps["inspect"]
    export = steps.get("export", {})
    restore = steps.get("restore", {})
    handoff = steps.get("handoff", {})

    lines = [
        f"### Observed {evidence['generated_at']}",
        "",
        f"- OS: `{env['os']}` ({env['machine']})",
        f"- Maya: `{probe['maya_version']}`, Python ABI `{probe['python_version']}`",
        f"- mayapy: `{probe['mayapy']}`",
        f"- module paths: {probe['module_path_count']}",
        "",
        "| Step | Result | Evidence |",
        "|---|---|---|",
        (
            f"| Probe | observed | Maya {probe['maya_version']} / Python "
            f"{probe['python_version']} |"
        ),
        (
            f"| Inspect | observed | camera `{inspect.get('approved_camera')}`, "
            f"{inspect.get('resolution')}, status `{inspect.get('inspection_status')}`, "
            f"deterministic={inspect.get('deterministic')} |"
        ),
        (
            f"| Playblast | observed | {export.get('dimensions')} @ {export.get('codec')}, "
            f"{export.get('duration_seconds')}s, {export.get('file_size_bytes')} bytes |"
        ),
        (
            f"| Restoration | observed | camera/frame-range/resolution/scene_id unchanged="
            f"{restore.get('camera_unchanged')}/{restore.get('frame_range_unchanged')}/"
            f"{restore.get('resolution_unchanged')}/{restore.get('scene_id_unchanged')} |"
        ),
        (
            f"| Bridge | {steps['bridge']['status']} | "
            f"{steps['bridge'].get('note') or 'link issued'} |"
        ),
        (
            f"| Handoff | {handoff.get('status')} | `{handoff.get('validator', 'n/a')}` "
            f"{'accepted' if not handoff.get('errors') else handoff.get('errors')} |"
        ),
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Maya runtime matrix")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--camera", default=None)
    parser.add_argument("--mode", default="white_model",
                        choices=("white_model", "material_preview"))
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=48)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--output-dir", default="/tmp/maya-matrix")
    parser.add_argument("--explicit-root", default=None)
    parser.add_argument("--search-path", default="")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--authorize-upload", action="store_true",
                        help="Also exercise the Jimeng link (explicit authorization)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", default=None,
                        help="Append the markdown evidence block to this file")
    args = parser.parse_args(argv)

    try:
        evidence = run_matrix(args)
    except maya_runner.MayaProbeError as exc:
        print(f"no usable Maya: {exc.code}: {exc}", file=sys.stderr)
        print("run: python3 scripts/maya_preflight.py", file=sys.stderr)
        return 1
    except (maya_runner.MayaRequestError, MatrixError, OSError, ValueError) as exc:
        print(f"matrix failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(evidence))

    if args.write:
        target = Path(args.write)
        block = render_markdown(evidence)
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        marker = "## Observed runs"
        if marker not in existing:
            existing = existing.rstrip() + f"\n\n{marker}\n\n"
        target.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")
        print(f"\nappended evidence to {target}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
