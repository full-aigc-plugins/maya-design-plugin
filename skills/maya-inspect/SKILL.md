---
name: maya-inspect
description: Read-only inspection of an authorized Autodesk Maya scene before any export or render. Produces a Codex scene receipt covering cameras, playback range, current time, resolution, active model panel, display mode, materials, references, namespaces, callbacks, and unknown plug-ins. Use when the user asks what a Maya scene contains, which cameras exist, what the frame range is, whether a scene has references or unknown plug-ins, or wants a dry-run inventory before exporting. Never mutates the scene, never loads plug-ins, never writes selection or current time. For exporting a preview use maya-export-preview instead; for a failure or missing-module question use maya-diagnose.
license: Apache-2.0 — see LICENSE
---

# maya-inspect — 即梦 Maya 场景只读检查

对一个**已授权**的 Maya 场景做只读盘点，产出一份 Codex `scene_receipt`。
不修改场景、不加载插件、不写选择集、不改当前帧。

## When to use / 什么时候使用

- 用户问「这个场景里有哪些相机 / 帧范围是多少 / 有没有引用文件」
- 导出前先做一次 dry-run 盘点，确认相机、分辨率、材质
- 需要把场景信息交给 `codex-dreamina-3d` 做后续编排
- 需要在不出图的前提下判断场景是否包含未知插件（`inspection_status` 会变成 `degraded`）

## When NOT to use / 不适用场景（不该用本技能）

- 需要出图 / 出视频 → 用 `maya-export-preview`
- 需要排查报错、模块缺失、ABI 不匹配 → 用 `maya-diagnose`
- 需要修改场景 → 本技能明确不支持；不要用本技能伪装成修改操作

## Rules

1. 只读。任何写操作（`select`、`currentTime(edit=True)`、`loadPlugin`、`setAttr`）在本技能路径上都会被拒绝。
2. 授权范围内操作。`scene_path` 必须是相对授权工程根目录的路径；绝对路径会在诊断信息中被脱敏为 `<redacted-path>`。
3. 确定性输出。同一场景重复检查必须产生逐字节相同的 JSON（`scene_id` 由场景路径的 SHA-256 派生，是确定性的）。
4. 不推断。场景里没有的信息不编造；缺失即标记 `inspection_status: degraded`。
5. 一次一个场景。不要在单次调用里检查多个场景然后合并回执。

## Workflow

真正的入口只有一条命令。**不要**自己拼 `mayapy` 命令行、不要调 `maya_bridge` 的函数——它只在 Maya 内部有效。

Step 1 — 运行检查（一条命令，driver 自己负责发现 Maya、argv 传参、超时与终止）：

```bash
python3 scripts/maya_runner.py inspect --scene <相对场景路径>
```

可选参数：`--explicit-root <Maya 安装根>`（Maya 不在标准位置时）、`--timeout <秒>`（默认 60）。

Step 2 — 读取 stdout 上的 `scene_receipt` JSON。失败时 driver 以非零退出并把
`{"code": ..., "message": ...}` 写到 stderr——**按 code 分支，不要解析自然语言**。

Step 3 — 用 `schemas/scene_receipt.schema.json` 校验回执：`display_mode` 在枚举内、
`frame_range.start <= end`、`resolution` 两项 ≥ 1。

Step 4 — 报告：向用户转述相机、帧范围、分辨率、材质数量、是否 degraded。
只有在用户明确要求时才把回执写文件。

### 底层调用链（排障时才需要了解）

```
python3 scripts/maya_runner.py inspect --scene <path>     ← 你调用的
  └─ maya_runner.discover_maya(...)                       ← 发现 mayapy
  └─ maya_runner.run_request(...)                         ← argv 启动子进程
       └─ mayapy scripts/maya_request.py <req> <resp>      ← Maya 内部入口
            └─ maya_bridge.inspect_scene(maya.cmds, ...)   ← 只读桥
```

`scripts/maya_runner.py` 是宿主侧 driver，`scripts/maya_request.py` 是 Maya 内部 runner。
`scripts/maya_bridge.py` 是纯库，直接运行它会以退出码 2 拒绝并提示正确的入口。

## Gotchas

1. `discover_maya` 在找不到 Maya 时抛 `MAYA_NOT_FOUND`，不要把它当成空场景处理。
2. Python ABI 不匹配（例如 Maya 2024 的 Python 3.7 vs 宿主 3.11）抛 `ABI_MISMATCH`，此时不要尝试安装 Python。
3. 场景里没有相机时抛 `SCENE_NOT_AUTHORIZED`，这是保护性行为——没有相机的场景无法导出，早失败比晚失败好。
4. `frame_range.start > end` 会在桥接层被拒绝。schema 只约束非负整数，业务规则在 `maya_bridge` 里。
5. `unknown_plugins` 非空会把 `inspection_status` 置为 `degraded`，这不是错误，是提示导出可能失败。
6. 中文路径（例如 `/Users/中文/scene.ma`）是支持的，桥接层按 UTF-8 处理；遇到编码报错请改用 `maya-diagnose`。
7. 不要为了「让检查通过」去修改场景。检查失败就是失败，如实报告。

## Validation

导出前自检清单（checklist）：

- [ ] `scene_id` 是 UUID v4 形状
- [ ] `plugin_id` 等于 `codex-maya`，`schema_version` 等于 `1.0.0`
- [ ] `display_mode` ∈ {`white_model`, `material_preview`, `existing_video`}
- [ ] `resolution.width` 与 `resolution.height` 都 ≥ 1
- [ ] `frame_range.start <= frame_range.end`
- [ ] 场景路径是相对路径（绝对路径只出现在被脱敏的诊断里）
- [ ] **verify** 两次调用产生完全相同的 JSON 字符串

## Safety declaration / 安全声明

本技能**不访问网络**、**不收集任何用户数据**、**不上传场景内容**、**不记录绝对路径**、**不安装任何软件包**。
它只读取用户显式授权的场景文件并在本机产生 JSON。诊断信息中的绝对路径一律脱敏为 `<redacted-path>`。

## References

需要更细的执行细节时加载以下文件：

- [references/workflows/inspection.md](references/workflows/inspection.md) — 完整检查流程与字段来源
- [references/workflows/determinism.md](references/workflows/determinism.md) — 确定性输出与 `scene_id` 派生规则
- [references/errors/error-catalog.md](references/errors/error-catalog.md) — 全部错误码与处置建议
- [references/errors/path-handling.md](references/errors/path-handling.md) — 中文路径与脱敏规则
