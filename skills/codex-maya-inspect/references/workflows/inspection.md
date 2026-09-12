# 场景检查完整流程

## 目的

在不出图的前提下，把 Maya 场景的可导出性盘点清楚，产出一份可被
`codex-dreamina-3d` 消费的 `scene_receipt`。

## 字段来源对照

| 回执字段 | Maya 来源 | 说明 |
|---|---|---|
| `scene_id` | 场景路径的 SHA-256 派生 | 确定性 UUID v4 形状 |
| `scene_path` | 调用方传入 | 必须是相对授权工程根的路径 |
| `approved_camera` | `cmds.listCameras()[0]` | 取第一个相机，保证确定性 |
| `frame_range.start` / `.end` | `cmds.playbackRange()` | 若 `start > end` 抛 `SCENE_NOT_AUTHORIZED` |
| `frame_range.current` | `cmds.currentTime(query=True)` | 只读，绝不写回 |
| `resolution.width` / `.height` | `cmds.getAttr("defaultResolution.*")` | 缺省 1920×1080 |
| `display_mode` | `cmds.getPanel("-type", "modelPanel")` + `getAttr(".displayMode")` | 映射到三值枚举 |
| `materials` | `cmds.ls("materials")` | 可为空 |
| `references` | `cmds.ls("references")` | 可为空 |
| `namespaces` | `cmds.ls("namespaces")` | 可为空 |
| `callbacks` | `cmds.ls("callbacks")` | 可为空 |
| `unknown_plugins` | `cmds.ls(type="unknownPlugin")` | 非空 → `degraded` |
| `inspection_status` | 由 `unknown_plugins` 推导 | `ok` 或 `degraded` |

## display_mode 映射规则

Maya 的 model panel `displayMode` 取值很多，回执只暴露三个值：

- `wireframe` → `white_model`
- 其他（`smoothShaded` 等）→ `material_preview`
- `existing_video` 只在本地上传模式出现，场景检查不会产生

没有任何 model panel 时，回执取 `material_preview` 作为安全缺省。

## 只读保证的实现方式

`inspect_scene` 进入时记录 `selection`、`currentTime`、已加载插件集合，
退出前再读一次并逐项比对；任何漂移都会抛 `RuntimeError`。
这意味着**代码里出现写操作会立刻在测试中暴露**，而不是等到线上才发现。

## 与导出的衔接

检查产出的 `scene_id` 会原样带到 `artifact_receipt.scene_id`，
这是两条链路之间唯一的关联键。不要重新生成 `scene_id`。
