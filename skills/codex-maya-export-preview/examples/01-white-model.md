# 示例 1：出白模预览

**用户说：** 「帮我出一版白模 review 视频，相机用 camera1，1 到 120 帧。」

**执行：** `codex-maya-export-preview`，`mode=white_model`，`camera=camera1`，
`start_frame=1`，`end_frame=120`

**输出：** `artifact_receipt`，`display_mode=white_model`，`restoration_status=restored`

**注意：** 120 帧 > 44 帧下限，通过配置校验。
