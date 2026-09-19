---
name: maya-diagnose
description: Diagnose Autodesk Maya plugin failures without installing anything. Classifies a Maya error, stack trace, or module-import failure into one of MAYA_NOT_FOUND, ABI_MISMATCH, MODULE_LOAD_FAILED, PATH_INVALID, or PYTHON_NOT_FOUND, and reports the observed Maya version, Python version, module path count, and redacted diagnostics. Use when the user reports a Maya error, asks why the plugin is failing, shares a ModuleNotFoundError, hits a Chinese-path problem, or sees a Python version mismatch between Maya and the host. Never installs packages, never modifies Maya's module search path, never rewrites the user environment, and never proposes a fix it did not verify. For exporting a preview use maya-export-preview instead; for a scene inventory use maya-inspect.
license: Apache-2.0 — see LICENSE
---

# maya-diagnose — 即梦 Maya 故障诊断

把 Maya 相关故障归类到固定错误码，输出**脱敏**诊断报告。
本技能只诊断、不修复、不安装。

## When to use / 什么时候使用

- 用户贴出 `ModuleNotFoundError`、`ImportError` 或一段 Maya 报错
- 用户问「为什么 Maya 插件跑不起来」
- 中文路径读取失败，需要区分「编码问题」还是「模块问题」
- 怀疑 Maya 的 Python 版本与宿主不匹配
- 导出失败后需要判断是环境问题还是场景问题

## When NOT to use / 不适用场景（不该用本技能）

- 需要导出视频 → 用 `maya-export-preview`（报错在导出阶段产生时，最终解释仍回到本技能）
- 需要盘点场景 → 用 `maya-inspect`
- 需要本技能**动手修**环境 → 本技能明确不做。它输出诊断，由用户决定装什么、改什么
- 想自动 `pip install` 缺失模块 → 不做。Python 包与 Maya 模块必须由用户显式安装

## Rules

1. **只诊断，不修复。** 输出结构化诊断，不执行任何修复动作。
2. **不安装。** 禁止 `pip install`、`ensurepip`、任何包管理器调用。
3. **不动 Maya 模块路径。** 禁止 `sys.path.append` / `sys.path.insert`。
4. **脱敏。** 绝对路径替换为 `<redacted-path>`；环境变量**只报类别与版本号，不报值**。
5. **稳定指纹。** 同一错误文本产生相同的 16 位指纹，便于日志关联。
6. **不推断。** 无法归类时返回 `DIAGNOSTICS_FAILED`，不要硬塞进某个类别。
7. **错误码是公开契约。** 改动错误码属于破坏性变更。

## Workflow

Step 1 — 收集输入：用户提供的错误文本或堆栈。没有输入时直接探测宿主环境。

Step 2 — 归类（`scripts/maya_diagnostics.py::probe_path`）：把文本匹配到五个类别之一，并计算稳定指纹。

Step 3 — 探测运行时（可选）：调用 `scripts/maya_runner.py::discover_maya` 拿到观察到的 Maya 版本、Python 版本、模块路径数量。

Step 4 — 组装报告（`diagnose`）：Python 运行时信息 + 脱敏后的 Maya 运行时摘要 + 模块路径（全部脱敏）。

Step 5 — 输出：把报告写到 stdout，并生成可复制的指纹。不写文件，除非用户明确要求。

Step 6 — 交接：向用户说明分类结论、观察到的版本号，以及**下一步由用户决定**的选项。

## Gotchas

1. `ModuleNotFoundError: No module named 'maya'` 在**宿主** Python 里是正常的——`maya` 模块只存在于 Maya 自带的 Python 中。不要因此判定安装损坏。
2. `ABI_MISMATCH` 时**不要**建议降级或升级宿主 Python。宿主与 Maya 是两个独立运行时。
3. `MAYA_NOT_FOUND` 时**不要**建议下载 Maya。Maya 是商业软件，必须用户自行安装与授权。
4. 中文路径失败**不一定是**编码问题。先看错误码：`PATH_INVALID` 才是路径类，`MODULE_LOAD_FAILED` 是模块类。
5. 报告里的 `module_path_count` 是**数量**不是列表内容——列表本身已逐条脱敏，但数量足以判断「模块路径是否为空」。
6. 指纹会归一化空白，因此「同一错误不同缩进」产生同一指纹，这是刻意的。
7. 不要为了让诊断「看起来有用」而编造修复步骤。不确定就说「需要用户确认」。
8. `PYTHON_NOT_FOUND` 与 `MAYA_NOT_FOUND` 的区别：前者是宿主 Python 缺失，后者是 Maya 缺失。

## Validation

诊断输出自检清单（checklist）：

- [ ] `category` 是六个合法值之一（含 `OK` 与 `DIAGNOSTICS_FAILED`）
- [ ] 报告中**不含**任何绝对路径（应全部为 `<redacted-path>`）
- [ ] 报告中**不含**环境变量的值
- [ ] `module_paths` 每一项都已脱敏
- [ ] `fingerprint` 为 16 位十六进制
- [ ] **verify** 同一输入两次调用产生完全相同的报告
- [ ] 报告**不含**未经验证的修复建议

## Safety declaration / 安全声明

本技能**不访问网络**、**不收集用户数据**、**不上传任何内容**、**不安装软件包**、
**不修改 Maya 模块搜索路径**、**不读写用户环境配置**。
它只读取当前进程与宿主环境的结构性信息（版本号、路径类别），
所有绝对路径与环境变量值在输出前一律脱敏。

## References

需要更细的执行细节时按需加载：

- [决策指南](references/decisions/decision-guide.md)
- [失败矩阵](references/operations/failure-matrix.md)
- [交付验证清单](references/operations/validation-checklist.md)

<!-- QUALITY_CONTRACT_START -->
## 什么时候使用

✅ 适用：

1. 用户明确要对 Maya 启动、模块、ABI、路径和运行时错误进行只读分诊。
2. 已提供或可安全取得必要上下文，需要得到可验证的 `maya-diagnostic-report`。
3. 需要按最小权限、可回滚方式执行，并保留审计证据。

⚠️ 先澄清：

1. 目标环境、授权边界或成功标准缺失时，先给出只读假设方案并列出缺失项。
2. 涉及生产环境变更时，先确认备份、维护窗口和回滚路径。
3. 输入可能含敏感信息时，只引用字段名和脱敏片段，不复制完整凭据。

❌ 不该用：

1. 自动安装 Maya、Python 包或在未授权时修改模块路径。
2. 用户只要概念解释且没有执行或交付需求。
3. 需要绕过鉴权、证书校验、人工确认或其他安全控制的请求。

## Workflow

Step 1：确认目标、环境、授权范围和不可变约束；信息不足时先产出带假设的只读版本。

Step 2：盘点现状与依赖，只读取必要数据，不记录令牌、密码、Cookie 或完整个人数据。

Step 3：选择最小影响路径，将高风险动作、外部网络调用和可逆步骤明确标注。

Step 4：生成或执行 `maya-diagnostic-report`，每一步都绑定输入、预期输出与失败条件。

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
- [ ] `错误类别、脱敏证据、影响范围和人工恢复步骤相互对应` 已由可复现证据验证。
- [ ] 敏感数据已脱敏，输出中没有完整凭据。
- [ ] 失败与超时路径已覆盖，未出现无限重试。
- [ ] 变更类任务具有备份或回滚说明。
- [ ] 最终结论区分事实、推断和未验证项。

## Gotchas

1. **授权不等于可达**：有权限但网络、证书或白名单不满足时，仍应停止并报告连接证据。
2. **成功码不等于业务成功**：必须检查 `错误类别、脱敏证据、影响范围和人工恢复步骤相互对应`，不能只看命令退出码或 HTTP 200。
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
