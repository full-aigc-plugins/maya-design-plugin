#!/usr/bin/env python3
"""Is a real Maya usable on this machine right now?

Read-only. Runs the same discovery the plugin uses in production, then reports
what it found, what is missing, and what to do about it. Never installs
anything and never modifies Maya.

Exit codes: 0 the runtime is usable, 1 no usable runtime, 2 discovery raised.

    python3 scripts/maya_preflight.py
    python3 scripts/maya_preflight.py --explicit-root /Applications/Autodesk/maya2026
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import maya_runner  # noqa: E402

# Autodesk's documented macOS support for Maya 2026 is 13.x-15.x. A machine
# newer than that is worth flagging: the install may work, but it is outside
# what Autodesk states, so a runtime failure there is not a plugin bug.
DOCUMENTED_MACOS_MAJORS = (13, 14, 15)

# Where Autodesk's macOS installer puts things by default.
DEFAULT_MACOS_ROOTS = (
    "/Applications/Autodesk/maya2026",
    "/Applications/Autodesk/maya2025",
    "/Applications/Autodesk/maya2024",
    "/Applications/Autodesk/Maya2026",
    "/Applications/Autodesk/Maya2025",
    "/Applications/Autodesk/Maya2024",
)


def _macos_version() -> tuple[int, ...] | None:
    try:
        out = subprocess.run(
            ["sw_vers", "-productVersion"], capture_output=True, text=True, timeout=10
        )
        if out.returncode == 0:
            return tuple(int(p) for p in out.stdout.strip().split(".") if p.isdigit())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def _candidate_roots(explicit: list[str]) -> list[Path]:
    roots: list[Path] = [Path(p) for p in explicit]
    env_root = os.environ.get("MAYA_LOCATION")
    if env_root:
        roots.append(Path(env_root))
    roots.extend(Path(p) for p in DEFAULT_MACOS_ROOTS)
    # A sibling directory next to the plugin, handy for a portable install.
    roots.append(Path(__file__).resolve().parents[1] / "maya")
    return roots


def _report_environment() -> dict:
    info = {
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    if sys.platform == "darwin":
        version = _macos_version()
        info["macos_version"] = ".".join(str(p) for p in version) if version else "unknown"
        if version and version[0] not in DOCUMENTED_MACOS_MAJORS:
            info["macos_outside_documented_range"] = (
                f"Autodesk documents macOS {DOCUMENTED_MACOS_MAJORS[0]}.x-"
                f"{DOCUMENTED_MACOS_MAJORS[-1]}.x for Maya 2026; this machine reports "
                f"{info['macos_version']}. Maya may still install and run, but a failure "
                f"here would be outside the supported matrix rather than a plugin bug."
            )
    return info


def _guidance() -> list[str]:
    return [
        "Maya is commercial software and is not distributed through any package "
        "manager (there is no Homebrew cask for it). The download is delivered "
        "through an Autodesk Account, so it has to be fetched and licensed by you:",
        "",
        "  1. Sign in or create an account at https://www.autodesk.com",
        "  2. Open https://www.autodesk.com/products/maya/free-trial (30 days, no "
        "credit card) or your Autodesk Account > Maya > Downloads",
        "  3. Pick macOS, the current version, and the Apple Silicon build",
        "  4. Run the installer (installs to /Applications/Autodesk/maya<year> by default)",
        "",
        "Then re-run this preflight. Nothing in this plugin installs, downloads, "
        "or licenses Maya for you, and it never will.",
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check whether a real Maya is usable")
    parser.add_argument("--explicit-root", action="append", default=[],
                        help="Maya install root to check (repeatable)")
    parser.add_argument("--search-path", default="")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args(argv)

    environment = _report_environment()

    try:
        runtime = maya_runner.discover_maya(
            args.explicit_root[0] if args.explicit_root else None, args.search_path
        )
    except maya_runner.MayaProbeError as exc:
        payload = {
            "usable": False,
            "code": exc.code,
            "message": str(exc),
            "environment": environment,
            "searched_roots": [str(p) for p in _candidate_roots(args.explicit_root)],
            "guidance": _guidance(),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("Maya is NOT usable on this machine.\n")
            print(f"  reason: {exc.code}: {exc}")
            print(f"  os:     {environment['os']}  ({environment['machine']})")
            if environment.get("macos_version"):
                print(f"  macOS:  {environment['macos_version']}")
            if environment.get("macos_outside_documented_range"):
                print("\n  ! " + environment["macos_outside_documented_range"])
            print("\n  searched:")
            for root in payload["searched_roots"]:
                print(f"    - {root}")
            print("\n" + "\n".join(_guidance()))
        return 1

    payload = {
        "usable": True,
        "mayapy": str(runtime.mayapy),
        "maya": str(runtime.maya) if runtime.maya else None,
        "version": runtime.version,
        "python_version": runtime.python_version,
        "module_path_count": len(runtime.module_paths),
        "environment": environment,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Maya is usable.\n")
        print(f"  mayapy        : {runtime.mayapy}")
        print(f"  maya          : {runtime.maya or '(not found, batch-only)'}")
        print(f"  maya version  : {runtime.version}")
        print(f"  python (ABI)  : {runtime.python_version}")
        print(f"  module paths  : {len(runtime.module_paths)}")
        print(f"  os            : {environment['os']}  ({environment['machine']})")
        if environment.get("macos_outside_documented_range"):
            print("\n  ! " + environment["macos_outside_documented_range"])
        print("\nNext: python3 scripts/run_runtime_matrix.py --scene <path> --camera <name>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
