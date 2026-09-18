---
name: maya-harness
description: "Maya calling spec: the read-only preflight and diagnostics boundary, MAYA_LOCATION resolution, reversible Playblast discipline, and the honest no-runtime posture. Read this before any Maya task."
---

# Maya 调用规范

执行通道：`scripts/` 下的确定性脚本（`maya_preflight.py` / `maya_diagnostics.py` /
`maya_bridge.py` / `maya_runner.py`）。**本插件无 MCP 服务器**——全部经脚本驱动。

## 1. 凭据与环境

- `MAYA_LOCATION`：Maya 安装位置（env/userConfig/默认探测三路）。
- **本机未装 Maya 时如实降级**：仅可运行只读预检（`maya_preflight`）与诊断；
  场景检查/Playblast 不可用，不要假装能跑。

## 2. 硬规则（来自上游验证记录）

- Playblast 不可逆动作需要显式授权；恢复路径先于提交。
- 场景自会话上次接触后被改动 → 旧预览作废（哈希失效），必须重新导出。
- 相机名带 `*Shape` 后缀时按用户原样传递，不自行规范。

## 3. 标准工作流

1. `maya_preflight` 只读预检（安装位置/Python/运行前置）。
2. `maya_inspect` 场景巡检 → `maya_export_preview` Playblast。
3. 出片交接走 `maya-seedance-pipeline`（volcengine/minimax 出片）。

## 4. 纪律

- 运行时声明必须来自实测（preflight 输出），"应该装了"不算数。
- 诊断失败原文上报；不编造 Maya 行为。
