# 示例 2：查询帧范围

**用户说：** 「这个镜头多少帧？」

**执行：** `codex-maya-inspect`

**输出要点：**
- `frame_range.start` / `.end` 来自 `cmds.playbackRange()`
- `frame_range.current` 来自 `cmds.currentTime(query=True)`，只读
- 若 `start > end`，抛 `SCENE_NOT_AUTHORIZED`，不要自动交换两端
