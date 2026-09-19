---
name: maya-use
description: Router for Maya integration workflows. Use when a Maya request is ambiguous or when the user asks what the plugin can do, how to start, or which Maya capability fits their goal - this Skill decides whether the request belongs to maya-inspect (read-only scene inventory), maya-export-preview (reversible Playblast export), or maya-diagnose (error classification without installing anything), then hands off. Also use for "打开 Maya 插件", "Maya 插件能做什么", "我该用哪个 Maya 功能", and other orientation questions. Do not use this Skill for a request that already maps to exactly one dedicated Skill - call that Skill directly instead. This Skill performs no Maya work itself, never invokes Maya, never installs software, and never modifies files outside its own directory.
license: Apache-2.0 — see LICENSE
---

# maya-use — 即梦 Maya 插件路由

这是一个**薄路由**技能。它自己不做任何 Maya 操作，只负责把请求交给
`maya-inspect` / `maya-export-preview` / `maya-diagnose`。

## When to use / 什么时候使用

- 用户问「这个 Maya 插件能做什么」「怎么开始」「我该用哪个功能」
- 用户的请求**同时可能属于多个技能**，需要先判断
- 用户只说「用一下 Maya 插件」而没说具体目标
- 需要一个总览式回答，帮助用户明确下一步

## When NOT to use / 不适用场景（不该用本技能）

- 请求已经明确属于某一个技能 → **直接调用那个技能**，不要绕经本路由
- 用户已经说了「检查场景」→ 用 `maya-inspect`
- 用户已经说了「渲染 / 出白模 / Playblast」→ 用 `maya-export-preview`
- 用户已经贴了报错 → 用 `maya-diagnose`

## 路由表

| 用户意图 | 交给 |
|---|---|
| 盘点场景：相机、帧范围、分辨率、材质、引用、命名空间、未知插件 | `maya-inspect` |
| 导出预览：白模 / 材质保留 / 已渲染本地视频登记 | `maya-export-preview` |
| 排查故障：报错分类、模块缺失、ABI 不匹配、中文路径 | `maya-diagnose` |

## Rules

1. **不重复细节。** 本技能正文**不复制**三个下游技能的工作流说明；只给路由判断。
2. **不越权。** 本技能不调用 Maya、不读写场景、不产生回执。
3. **一次只路由一个目标。** 如果一个请求确实需要两个技能（例如「先检查再导出」），明确告知用户这是两步，并给出顺序。
4. **明确说明顺序。** 组合场景的标准顺序是：先 `inspect`（dry-run 盘点）→ 再 `export-preview`（出图）→ 失败则 `diagnose`。
5. **不猜。** 用户目标不清晰时，用一句话确认目标，而不是替用户选一个技能硬跑。

## Workflow

Step 1 — 读取用户请求，判断意图类别：盘点 / 导出 / 排障 / 不确定。

Step 2 — 若属于前三类之一，直接给出目标技能名并说明理由（一句话）。

Step 3 — 若属于「不确定」，向用户提一个澄清问题（例如「你是想先看看场景里有什么，还是直接出图？」）。

Step 4 — 若是组合场景，给出两步或三步的顺序，并说明每步的产出。

Step 5 — 交给目标技能。本技能到此结束，不继续执行下游动作。

## Gotchas

1. **不要**因为本技能名字带 `use` 就以为它是入口必备。它只在**模糊请求**时使用；明确请求直接走对应技能，少绕一圈。
2. **不要**在本技能里写下游技能的完整流程。那会造成两份真相，改一处漏一处。
3. 组合场景（先检查再导出）**不是**一次调用能完成的，必须分成两次，且 `scene_id` 要在两步之间原样传递。
4. 用户说「用一下即梦插件」时，多半真正的目标是**导出预览**；确认一句再路由，不要直接开跑。
5. 本技能不产生任何回执；如果用户期待回执，说明他真正需要的是下游技能。
6. 中文与英文请求都可以路由；路由判断只看意图，不看语言。
7. 用户提到「上传到即梦」时，路由到 `maya-export-preview`；必须先获得明确上传
   授权，插件只生成网页链接，不代替用户登录或确认付费生成。

## Validation

路由决策自检清单（checklist）：

- [ ] 是否确认了请求**不属于**单一明确技能？（否则不该用本技能）
- [ ] 路由目标是否是三个技能之一？
- [ ] 是否给出了**顺序**（组合场景）或**理由**（单一场景）？
- [ ] 是否**没有**复制下游技能的工作流细节？
- [ ] 是否**没有**调用任何 Maya 接口？
- [ ] **verify** 本技能正文行数保持在「薄」的量级，不随下游技能膨胀

## Safety declaration / 安全声明

本技能**不访问网络**、**不收集用户数据**、**不上传任何内容**、**不安装软件**、
**不调用 Maya**、**不读写场景文件**。它只输出路由文本，不产生副作用。

## References

需要更细的路由判断时按需加载：

- [决策指南](references/decisions/decision-guide.md)
- [失败矩阵](references/operations/failure-matrix.md)
- [交付验证清单](references/operations/validation-checklist.md)

<!-- QUALITY_CONTRACT_START -->
## 什么时候使用

✅ 适用：

1. 用户明确要在 Maya 检查、预览导出和故障诊断技能之间做零副作用路由。
2. 已提供或可安全取得必要上下文，需要得到可验证的 `maya-skill-routing-decision`。
3. 需要按最小权限、可回滚方式执行，并保留审计证据。

⚠️ 先澄清：

1. 目标环境、授权边界或成功标准缺失时，先给出只读假设方案并列出缺失项。
2. 涉及生产环境变更时，先确认备份、维护窗口和回滚路径。
3. 输入可能含敏感信息时，只引用字段名和脱敏片段，不复制完整凭据。

❌ 不该用：

1. 代替专项技能执行 Maya 操作或在目标已明确时增加无意义路由。
2. 用户只要概念解释且没有执行或交付需求。
3. 需要绕过鉴权、证书校验、人工确认或其他安全控制的请求。

## Workflow

Step 1：确认目标、环境、授权范围和不可变约束；信息不足时先产出带假设的只读版本。

Step 2：盘点现状与依赖，只读取必要数据，不记录令牌、密码、Cookie 或完整个人数据。

Step 3：选择最小影响路径，将高风险动作、外部网络调用和可逆步骤明确标注。

Step 4：生成或执行 `maya-skill-routing-decision`，每一步都绑定输入、预期输出与失败条件。

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
- [ ] `唯一目标技能、选择理由、必要顺序和交接字段明确` 已由可复现证据验证。
- [ ] 敏感数据已脱敏，输出中没有完整凭据。
- [ ] 失败与超时路径已覆盖，未出现无限重试。
- [ ] 变更类任务具有备份或回滚说明。
- [ ] 最终结论区分事实、推断和未验证项。

## Gotchas

1. **授权不等于可达**：有权限但网络、证书或白名单不满足时，仍应停止并报告连接证据。
2. **成功码不等于业务成功**：必须检查 `唯一目标技能、选择理由、必要顺序和交接字段明确`，不能只看命令退出码或 HTTP 200。
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
