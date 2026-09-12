# 六步导出流水线

| 步 | 动作 | 失败错误码 |
|---|---|---|
| 1 | 确认模式 | `SCENE_NOT_AUTHORIZED`（模式非法） |
| 2 | 发现 Maya | `MAYA_NOT_FOUND` / `ABI_MISMATCH` / `MODULE_LOAD_FAILED` |
| 3 | 恢复性导出（快照 → 配置 → Playblast → 还原） | `CAMERA_NOT_FOUND` / `PLAYBLAST_FAILED` / `RESTORE_UNCONFIRMED` |
| 4 | 组装回执 | — |
| 5 | 媒体验证 | `MEDIA_INVALID` |
| 6 | 报告 | — |

## 阶段 3 的内部顺序

```
restored_maya_state(cmds)            ← 进入：快照 11 个字段
  ├─ playblast.run_playblast(...)    ← 即梦实现；内部还有一层 ViewportPreviewState
  │     └─ ViewportPreviewState      ← 还原 29 个视口 flag + 选择集 + 当前帧
  └─ upload_bridge.start_local_bridge(...)  ← 启动 127.0.0.1 本地网桥
                                       ← 退出：还原并逐字段比对
```

## 为什么嵌套两层还原

即梦的 `ViewportPreviewState` 覆盖**视口层**（29 个 model editor flag）。
Codex 外层的 `restored_maya_state` 覆盖**场景层**（渲染器、图像格式、分辨率、播放范围、着色器覆盖）。
两者互补，合起来才是完整还原。
