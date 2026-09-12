# 示例 3：登记已有视频

**用户说：** 「我已经有一段渲染好的 mp4，帮我登记进流水线。」

**执行：** `codex-maya-export-preview`，`mode=existing_video`，`video_path=/path/clip.mp4`

**输出：** `display_mode=existing_video`，`restoration_status=restored`

**注意：** 此模式**完全不碰 Maya**，不启动 `restored_maya_state`。
