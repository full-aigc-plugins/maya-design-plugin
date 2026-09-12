# 示例 3：ABI 不匹配

**用户说：** 「我的 mayapy 是 Python 3.11。」

**执行：** `codex-maya-diagnose`

**输出：** `category: ABI_MISMATCH`，观察到的 Python 版本 `3.11`

**关键说明：** 支持区间是 Python 3.7（Maya 2022–2024）。
**不要**建议改宿主 Python，也**不要**建议降级 mayapy。
