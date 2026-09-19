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

需要更细的执行细节时按需加载：

- [决策指南](references/decisions/decision-guide.md)
- [失败矩阵](references/operations/failure-matrix.md)
- [交付验证清单](references/operations/validation-checklist.md)

<!-- QUALITY_CONTRACT_START -->
## 什么时候使用

✅ 适用：

1. 用户明确要只读检查 Maya 场景并生成确定性的场景回执。
2. 已提供或可安全取得必要上下文，需要得到可验证的 `maya-scene-receipt`。
3. 需要按最小权限、可回滚方式执行，并保留审计证据。

⚠️ 先澄清：

1. 目标环境、授权边界或成功标准缺失时，先给出只读假设方案并列出缺失项。
2. 涉及生产环境变更时，先确认备份、维护窗口和回滚路径。
3. 输入可能含敏感信息时，只引用字段名和脱敏片段，不复制完整凭据。

❌ 不该用：

1. 修改场景、创建相机、修复材质或启动渲染。
2. 用户只要概念解释且没有执行或交付需求。
3. 需要绕过鉴权、证书校验、人工确认或其他安全控制的请求。

## Workflow

Step 1：确认目标、环境、授权范围和不可变约束；信息不足时先产出带假设的只读版本。

Step 2：盘点现状与依赖，只读取必要数据，不记录令牌、密码、Cookie 或完整个人数据。

Step 3：选择最小影响路径，将高风险动作、外部网络调用和可逆步骤明确标注。

Step 4：生成或执行 `maya-scene-receipt`，每一步都绑定输入、预期输出与失败条件。

Step 5：校验结构、事实来源和目标状态；禁止根据缺失证据编造成功结论。

Step 6：失败时停止扩大影响，输出已完成步骤、失败证据、恢复点和下一次安全重试条件。

Step 7：交付摘要、验证证据、剩余风险与后续动作；生产变更必须说明回滚是否已验证。

## Rules

- 默认只读；写操作、高危操作和付费调用必须获得与该动作匹配的明确授权。
- 本技能不收集、不存储、不上传用户凭据；日志和报告不得包含完整 token、密码或密钥。
- 不关闭 TLS 校验，不执行来源不明脚本，不使用管道下载后直接执行。
- 只把真实执行结果写成“已完成”；计划、示例和推断必须显式标注。
- 优先幂等操作；无法幂等时先提供预演、备份和回滚点。

## Validation checklist

- [ ] 目标、环境与授权范围均已写明。
- [ ] `scene_id、相机、帧范围、分辨率、引用、命名空间和警告均有可复查来源` 已由可复现证据验证。
- [ ] 敏感数据已脱敏，输出中没有完整凭据。
- [ ] 失败与超时路径已覆盖，未出现无限重试。
- [ ] 变更类任务具有备份或回滚说明。
- [ ] 最终结论区分事实、推断和未验证项。

## Gotchas

1. **授权不等于可达**：有权限但网络、证书或白名单不满足时，仍应停止并报告连接证据。
2. **成功码不等于业务成功**：必须检查 `scene_id、相机、帧范围、分辨率、引用、命名空间和警告均有可复查来源`，不能只看命令退出码或 HTTP 200。
3. **重试不等于恢复**：对鉴权失败、参数错误和安全拒绝不得盲目重试。
4. **示例不等于现状**：模板值与占位符不能写成真实环境数据。
5. **输出不等于交付**：还需完成结构校验、风险说明和可重复验证。
6. **跨环境不可照搬**：操作系统、版本、区域和宿主能力不同时必须重新确认参数。

## 渐进式资料

- 做路径选择前读取 `references/decisions/decision-guide.md`。
- 遇到异常、超时或部分成功时读取 `references/operations/failure-matrix.md`。
- 完成交付前读取 `references/operations/validation-checklist.md`。
- 需要可复制输入时，按顺序参考 `examples/basic.md`、`examples/failure.md`、`examples/advanced.md`。
<!-- QUALITY_CONTRACT_END -->
