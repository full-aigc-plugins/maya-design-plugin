#!/usr/bin/env python3
"""UserPromptSubmit hook: point Maya-shaped requests at the plugin commands.

Advisory only — always exits 0; silent unless the prompt looks Maya-related.
"""
from __future__ import annotations

import json
import re
import sys

INTENT_RE = re.compile(
    r"maya|玛雅|playblast|拍屏|预览动画|绑骨|蒙皮|骨骼绑定|\bmel\b|场景诊断",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    prompt = ""
    if isinstance(payload, dict):
        prompt = str(payload.get("prompt") or "")

    if prompt.strip().startswith("/"):
        return 0

    if INTENT_RE.search(prompt):
        print(
            "提示：该请求疑似 Maya 相关。可用 /maya 总入口或细分命令 "
            "(/maya-inspect /maya-export-preview /maya-diagnose)；"
            "本机未装 Maya 时仅支持只读预检与诊断。"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
