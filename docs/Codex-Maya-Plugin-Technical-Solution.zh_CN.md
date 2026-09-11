# Codex Maya 插件技术方案

> 设计阶段方案，2026-09-11。

## 技术决策

采用 Codex Skill 层、仅 argv 的运行器，以及支持批处理检查和受控 Playblast 的 Maya Python Bridge。不复制官方 Dreamina Maya 上传器。

## 目标目录

```text
.codex-plugin/plugin.json
skills/codex-maya-*/
scripts/maya_runner.py
scripts/maya_bridge.py
scripts/media_probe.py
schemas/
tests/
```

## 核心机制

- 发现 `maya`、`mayapy`、版本、Python ABI 和模块路径。
- 首先生成只读场景回执。
- 快照选择集、当前时间、播放范围、活动视图、相机、显示模式和输出设置。
- 在临时目录生成白模或材质预览 Playblast。
- 只使用已存在且获准的媒体工具转换。
- 恢复状态，并原子发布验证后的结果。

## 错误模型

`MAYA_NOT_FOUND`、`ABI_MISMATCH`、`MODULE_LOAD_FAILED`、`SCENE_NOT_AUTHORIZED`、`CAMERA_NOT_FOUND`、`PLAYBLAST_FAILED`、`TIMEOUT`、`RESTORE_UNCONFIRMED`、`MEDIA_INVALID`。

## 测试策略

使用 fake `maya.cmds` 做单元 TDD，用 fixture 脚本验证批处理行为，覆盖 Unicode 路径，并将真实 Maya 冒烟测试作为独立授权门禁。模块能导入不等于运行验收通过。
