# 示例 3：先检查再导出

**用户说：** 「先看看这个场景，然后出一版白模。」

**执行：** `codex-maya-use` 说明这是两步

**输出：**
1. `codex-maya-inspect` → 拿到 `scene_id`
2. `codex-maya-export-preview`（`scene_id` 原样传递）

**关键：** 两次调用，不是一次。
