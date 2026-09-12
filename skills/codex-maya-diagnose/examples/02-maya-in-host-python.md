# 示例 2：宿主 Python 里 import maya

**用户贴出：** `ModuleNotFoundError: No module named 'maya'`（跑在 Python 3.13）

**执行：** `codex-maya-diagnose`

**输出：** `category: MODULE_LOAD_FAILED`，但必须补充解释

**关键说明：** 这是**正常现象**。`maya` 只存在于 Maya 自带的 Python 3.7 里。
不要判定安装损坏。
