# 组合场景的顺序与 scene_id 传递

## 标准两步

```
codex-maya-inspect  →  scene_receipt (含 scene_id)
                            │
                            ▼ (原样传递 scene_id)
codex-maya-export-preview  →  artifact_receipt (含同一个 scene_id)
```

## 三步（带排障）

```
inspect → export-preview → (失败) → diagnose
```

## 关键约束

1. **两次调用，不是一次。** 不能在一次技能调用里既检查又导出。
2. **`scene_id` 原样传递。** 导出阶段**不得**重新生成 `scene_id`。
3. **失败即停。** 检查失败就不要进入导出；导出失败就不要假装有回执。
4. **报告进度。** 告诉用户「这是两步中的第一步」。
