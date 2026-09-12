# 错误码目录（导出）

| 错误码 | 触发阶段 | 含义 | 处置 |
|---|---|---|---|
| `SCENE_NOT_AUTHORIZED` | 模式确认 | 模式非法，或 `existing_video` 的文件不存在 | 修正模式或路径 |
| `MAYA_NOT_FOUND` | 发现 | 没有可用 Maya | 用户指定安装位置 |
| `ABI_MISMATCH` | 发现 | Maya 的 Python ABI 不在支持区间 | 换受支持的 Maya 版本 |
| `MODULE_LOAD_FAILED` | 发现 | Maya 模块路径异常 | 用户在 Maya 内确认安装完整 |
| `CAMERA_NOT_FOUND` | 导出 | 指定相机名不存在 | 先 `codex-maya-inspect` 确认相机名 |
| `PLAYBLAST_FAILED` | 导出 | 捕获/转换/校验/发布任一阶段失败 | 看错误信息里的阶段名 |
| `RESTORE_UNCONFIRMED` | 还原 | 场景未回到导出前状态 | **立即报告，不重试** |
| `MEDIA_INVALID` | 验证 | 产物不满足容器/编解码/尺寸约束 | 检查导出参数与磁盘空间 |
| `TIMEOUT` | 任意 | 超出超时预算 | 缩短帧范围后重新发起 |

## 错误码分层

- **发现层**：`MAYA_NOT_FOUND` / `ABI_MISMATCH` / `MODULE_LOAD_FAILED`
- **执行层**：`CAMERA_NOT_FOUND` / `PLAYBLAST_FAILED` / `TIMEOUT`
- **完整性层**：`RESTORE_UNCONFIRMED` / `MEDIA_INVALID`

`RESTORE_UNCONFIRMED` 是唯一一个**必须停下来问用户**的错误码——
场景状态未知，继续操作可能污染用户的工程。
