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
