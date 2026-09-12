# 状态快照与还原机制

## 双层还原

还原是**分层**的，两层各有明确职责：

| 层 | 实现 | 覆盖范围 |
|---|---|---|
| 外（场景层） | `maya_bridge.restored_maya_state` | 渲染器、图像格式、分辨率、播放范围，以及对下层的**校验 pass** |
| 内（视口层） | 即梦 `ViewportPreviewState` | 29 个 model editor flag + 选择集 + 当前帧 |

内层是即梦官方实现，Codex 侧**原样复用，不重写**。

## 快照的十个字段（外层）

| 字段 | 读取方式 | 还原方式 |
|---|---|---|
| `selection` | `cmds.ls(selection=True, long=True)` | `select(clear=True)` + `select(values, replace=True)` |
| `current_time` | `cmds.currentTime(query=True)` | `cmds.currentTime(v, edit=True)` |
| `playback_range` | `cmds.playbackOptions(query=True, minTime/maxTime)` | `playbackOptions(edit=True, ...)` |
| `camera` | active panel 的 `camera` | `modelPanel(edit=True, camera=...)` |
| `active_panel` | `cmds.getPanel(withFocus=True)` | 运行时概念，无需还原 |
| `display_appearance` | active panel 的 `displayAppearance` | `modelPanel(edit=True, displayAppearance=...)` |
| `display_textures` | active panel 的 `displayTextures` | `modelPanel(edit=True, displayTextures=...)` |
| `renderer` | `defaultRenderGlobals.currentRenderer` | `setAttr(...)` |
| `image_format` | `defaultRenderGlobals.imageFormat` | `setAttr(...)` |
| `resolution` | `defaultResolution.width/height` | `setAttr(...)` |

## 为什么有五个字段两层都覆盖

`selection` / `current_time` / `camera` / `display_appearance` / `display_textures`
同时出现在两层。这不是重复实现，而是**分工**：

- **内层负责真正还原**它们（即梦实现已经这么做，Codex 侧不重写）
- **外层的校验 pass 负责确认**它们回到了原位

没有外层校验，就没有办法发现「内层静默还原失败」，
`artifact_receipt.restoration_status` 也就无从判断。

## 关于着色器

即梦实现做白模靠的是视口的 `useDefaultMaterial` **flag**，
**不创建也不指派任何临时着色器**。因此流程里不存在「临时着色器覆盖」，
自然也没有需要还原的着色器状态。

早期版本曾把这个字段列为待还原项，但它对应的操作在真实流程中不发生，
属于虚假声明，已移除。教训：文档里列的字段必须能在代码里找到对应实现。

## 还原的失败处理

`_restore_snapshot` 对每个字段单独 `try/except`，**任一字段还原失败不中断其他字段**。
全部尝试完成后，`restored_maya_state` 再读一次快照并逐字段比对；
只要有漂移就抛 `RESTORE_UNCONFIRMED`。

## 为什么这个顺序

先尽力还原所有字段，再统一校验。这样即使用户看到一个错误，
也知道「哪些字段还原了、哪些没有」，而不是第一个错误就中断、
后面字段的状态未知。
