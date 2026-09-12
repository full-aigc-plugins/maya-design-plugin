# scene_receipt 字段全表

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `schema_version` | string | 固定 `1.0.0` | 契约版本 |
| `plugin_id` | string | 固定 `codex-maya` | 插件身份 |
| `scene_id` | string | UUID v4 形状 | 由场景路径 SHA-256 派生 |
| `scene_path` | string | 非空 | 相对授权工程根 |
| `approved_camera` | string | 非空 | 相机列表第一项 |
| `frame_range` | object | 闭合 | `start`/`end`/`current` 均 ≥ 0 |
| `resolution` | object | 闭合 | `width`/`height` 均 ≥ 1 |
| `display_mode` | string | 三值枚举 | `white_model` / `material_preview` / `existing_video` |
| `materials` | array[string] | 可为空 | 材质节点名 |
| `references` | array[string] | 可为空 | 引用文件名 |
| `namespaces` | array[string] | 可为空 | 命名空间 |
| `callbacks` | array[string] | 可为空 | 回调名 |
| `unknown_plugins` | array[string] | 可为空 | 未知插件名 |
| `inspection_status` | string | `ok` / `degraded` | 由 `unknown_plugins` 推导 |

## 闭合约束

`frame_range` 与 `resolution` 设了 `additionalProperties: false`，
顶层同样闭合。这意味着**新增字段必须改 schema**，不能偷偷塞进去。
