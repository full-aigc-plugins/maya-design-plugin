#!/usr/bin/env python3
"""SessionStart hook: report Maya readiness for this plugin.

Advisory only — always exits 0. On hosts without Maya the plugin still
serves read-only preflight/diagnostics, which this summary states honestly.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys
from pathlib import Path

MAYA_GLOBS = [
    "/Applications/Autodesk/maya*/Maya.app/Contents/MacOS/Maya",
    "/Applications/Autodesk/maya*/Maya.app",
]


def find_maya() -> str:
    explicit = os.environ.get("MAYA_LOCATION")
    if explicit and Path(explicit).exists():
        return explicit
    for pattern in MAYA_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return shutil.which("maya") or ""


def main() -> int:
    lines: list[str] = []

    maya = find_maya()
    if maya:
        lines.append(f"Maya: {maya}")
    else:
        lines.append("Maya: 未找到——场景检查/Playblast 不可用，仅可运行只读预检（maya_preflight）与诊断")

    lines.append(f"python3: {sys.version.split()[0]}")

    preflight = Path(__file__).resolve().parents[1] / "scripts" / "maya_preflight.py"
    lines.append("预检脚本: 就绪" if preflight.is_file() else "预检脚本: 缺失")

    try:
        sys.stdin.read()
    except Exception:
        pass

    print("Maya 插件环境：" + "；".join(lines))
    return 0


if __name__ == "__main__":
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    sys.exit(main())
