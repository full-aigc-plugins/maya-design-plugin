---
name: codex-maya-use
description: Router for the Codex Maya plugin. Use when a Maya request is ambiguous or when the user asks what the plugin can do, how to start, or which Maya capability fits their goal - this Skill decides whether the request belongs to codex-maya-inspect (read-only scene inventory), codex-maya-export-preview (reversible Playblast export), or codex-maya-diagnose (error classification without installing anything), then hands off. Also use for "打开 Maya 插件", "Maya 插件能做什么", "我该用哪个 Maya 功能", and other orientation questions. Do not use this Skill for a request that already maps to exactly one dedicated Skill - call that Skill directly instead. This Skill performs no Maya work itself, never invokes Maya, never installs software, and never modifies files outside its own directory.
license: Apache-2.0 — see LICENSE
---

# codex-maya-use — 即梦 Maya 插件路由

这是一个**薄路由**技能。它自己不做任何 Maya 操作，只负责把请求交给
`codex-maya-inspect` / `codex-maya-export-preview` / `codex-maya-diagnose`。

## When to use / 什么时候使用

- 用户问「这个 Maya 插件能做什么」「怎么开始」「我该用哪个功能」
- 用户的请求**同时可能属于多个技能**，需要先判断
- 用户只说「用一下 Maya 插件」而没说具体目标
- 需要一个总览式回答，帮助用户明确下一步

## When NOT to use / 不适用场景（不该用本技能）

- 请求已经明确属于某一个技能 → **直接调用那个技能**，不要绕经本路由
- 用户已经说了「检查场景」→ 用 `codex-maya-inspect`
- 用户已经说了「渲染 / 出白模 / Playblast」→ 用 `codex-maya-export-preview`
- 用户已经贴了报错 → 用 `codex-maya-diagnose`

## 路由表

| 用户意图 | 交给 |
|---|---|
| 盘点场景：相机、帧范围、分辨率、材质、引用、命名空间、未知插件 | `codex-maya-inspect` |
| 导出预览：白模 / 材质保留 / 已渲染本地视频登记 | `codex-maya-export-preview` |
| 排查故障：报错分类、模块缺失、ABI 不匹配、中文路径 | `codex-maya-diagnose` |

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
7. 用户提到「上传到即梦」时，导出与上传是分开的：本插件只做本地导出，云端上传由 `codex-dreamina-3d` 负责。

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

需要更细的路由判断细节时加载以下文件：

- [references/workflows/routing.md](references/workflows/routing.md) — 路由判断详解
- [references/workflows/composition.md](references/workflows/composition.md) — 组合场景的顺序与 scene_id 传递
- [references/workflows/anti-routing.md](references/workflows/anti-routing.md) — 什么情况下**不该**用本技能
- [references/errors/misroute-recovery.md](references/errors/misroute-recovery.md) — 路由错了怎么回退
- [references/errors/ambiguous-requests.md](references/errors/ambiguous-requests.md) — 模糊请求的澄清话术
- [references/schemas/skill-boundaries.md](references/schemas/skill-boundaries.md) — 四个技能的能力边界对照
- [references/schemas/handoff-contract.md](references/schemas/handoff-contract.md) — 技能之间的交接契约
- [references/safety/zero-side-effect.md](references/safety/zero-side-effect.md) — 零副作用保证
- [references/safety/no-duplication.md](references/safety/no-duplication.md) — 不重复原则
- [references/workflows/quickstart.md](references/workflows/quickstart.md) — 三步上手
