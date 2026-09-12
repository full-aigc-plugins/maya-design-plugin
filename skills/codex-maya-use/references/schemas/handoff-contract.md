# 技能之间的交接契约

## inspect → export-preview

**传递：** `scene_id`（UUID v4 字符串）

**约束：** 原样传递，不重新生成。

**为什么：** `codex-dreamina-3d` 用 `scene_id` 把检查与产物配对。

## export-preview → diagnose

**传递：** 错误码 + 错误消息

**约束：** 原样传递错误码，不要改写。

## diagnose → 用户

**传递：** 脱敏报告 + 指纹

**约束：** 不传修复建议（诊断技能不提供未经验证的修复）。

## use → 任意下游

**传递：** 路由目标名

**约束：** 只传目标，不传参数——参数由下游技能自己校验。

## 共同契约

所有技能共享：

- `plugin_id = "codex-maya"`
- `schema_version = "1.0.0"`
- 错误码是稳定的公开字符串
