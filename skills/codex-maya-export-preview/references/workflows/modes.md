# 三种模式对比

| 维度 | `white_model` | `material_preview` | `existing_video` |
|---|---|---|---|
| 是否调用 Maya | 是 | 是 | **否** |
| 是否改动场景 | 临时改动并还原 | 临时改动并还原 | 完全不碰 |
| 材质处理 | 用默认材质（白模） | 保留场景材质与贴图 | 不适用 |
| 帧数下限 44 | 适用 | 适用 | 不适用 |
| `restoration_status` | `restored` | `restored` | 恒 `restored` |
| 典型用途 | 结构 review、快速预览 | 材质/配色 review | 登记已渲染片段 |
| 对应即梦参数 | `useDefaultMaterial=True` | `useDefaultMaterial=False` | — |

## 自动选择

即梦实现里有 `preview_mode_for_scene()`：扫描场景网格，若发现用户材质或
贴图连接，则倾向 `material`，否则 `solid`（白模）。

Codex 侧的显式 `mode` 参数**优先**于自动检测。用户说「要白模」就出白模，
即使场景里有材质。

## existing_video 的边界

`existing_video` 只做三件事：校验文件存在、计算 SHA-256、拼装回执。
它**不调用 ffmpeg**（`.mp4` 直接登记；非 `.mp4` 由即梦的
`mp4_upload_path` 处理——但那属于导出路径，不在本模式的 Codex 契约里）。
