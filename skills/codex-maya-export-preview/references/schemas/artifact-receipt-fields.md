# artifact_receipt 字段全表

| 字段 | 类型 | 约束 | 来源 |
|---|---|---|---|
| `schema_version` | string | 固定 `1.0.0` | 常量 |
| `plugin_id` | string | 固定 `codex-maya` | 常量 |
| `artifact_id` | string | UUID v4 | 每次导出新生成 |
| `scene_id` | string | UUID v4 | **从检查阶段原样传入** |
| `media_path` | string | 非空 | 产物路径 |
| `media_format` | string | 固定 `video/mp4` | 常量 |
| `media_sha256` | string | `^[0-9a-f]{64}$` | 分块计算 |
| `duration_seconds` | number | ≥ 0 | `mvhd` 或帧数/fps |
| `frame_rate` | number | > 0 | 导出参数或 DCC 协议 |
| `width` / `height` | integer | ≥ 1 | 导出参数 |
| `file_size_bytes` | integer | ≥ 0 | 文件系统 |
| `restoration_status` | string | 三值枚举 | 还原校验结果 |
| `display_mode` | string | 三值枚举 | 导出模式 |

## 与即梦协议的关系

`media_format` 固定 `video/mp4`、`duration_seconds` 上限 30 秒、
`file_size_bytes` 上限 200 MiB —— 这三条来自即梦 DCC 协议
（`dcc_config.FALLBACK_RESPONSE_DATA`），不是本地随意设定。

## 明确不包含的字段

| 字段 | 为什么排除 |
|---|---|
| `redirect_url` | 内嵌 token，属会话凭据 |
| `resource_info_url` | 同上 |
| `port` / `pid` / `helper_pid` | 进程内部信息，对下游无意义 |
| `expires_at` | 与 token 同生命周期 |
