# 示例 4：导出前 dry-run

**用户说：** 「先别出图，告诉我这个场景导出来会是什么样。」

**执行：** `codex-maya-inspect` → 报告 → 用户确认后再走 `codex-maya-export-preview`

**输出要点：**
- 报告分辨率、帧范围、display_mode、材质数量
- `display_mode` 会告诉用户「会不会是白模」
- 用户确认后，把 `scene_id` 原样传给导出技能
