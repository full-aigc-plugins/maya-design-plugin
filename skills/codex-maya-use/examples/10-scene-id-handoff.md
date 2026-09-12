# 示例 10：scene_id 交接

**用户说：** 「检查完直接出图，别让我再传一次参数。」

**执行：** 说明必须两步，但 Agent 会**自动传递** `scene_id`

**输出：**
1. 跑 `codex-maya-inspect` → 拿 `scene_id`
2. 跑 `codex-maya-export-preview`，把 `scene_id` 填进去

**关键：** 用户不需要手动传，但两步骤依然存在。
