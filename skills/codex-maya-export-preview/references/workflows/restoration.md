# 状态快照与还原机制

## 快照的十一个字段

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
| `shader_overrides` | 着色器覆盖表 | 逐项还原 |

## 还原的失败处理

`_restore_snapshot` 对每个字段单独 `try/except`，**任一字段还原失败不中断其他字段**。
全部尝试完成后，`restored_maya_state` 再读一次快照并逐字段比对；
只要有漂移就抛 `RESTORE_UNCONFIRMED`。

## 为什么这个顺序

先尽力还原所有字段，再统一校验。这样即使用户看到一个错误，
也知道「哪些字段还原了、哪些没有」，而不是第一个错误就中断、
后面字段的状态未知。
