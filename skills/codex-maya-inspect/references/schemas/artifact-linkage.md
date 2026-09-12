# 与 artifact_receipt 的关联

两个回执通过 `scene_id` 关联：

```
scene_receipt.scene_id  ──┐
                          ├─→ 同一个 UUID
artifact_receipt.scene_id ┘
```

## 规则

1. 检查阶段生成的 `scene_id` 必须原样带入导出阶段。
2. 导出技能**不得**重新生成 `scene_id`。
3. 两者 `plugin_id` 与 `schema_version` 必须一致（都是 `codex-maya` / `1.0.0`）。

## 为什么

`codex-dreamina-3d` 用 `scene_id` 把「检查过的场景」和「产出的视频」配对。
如果导出时重新生成 ID，下游就找不到对应关系，用户会看到孤立产物。
