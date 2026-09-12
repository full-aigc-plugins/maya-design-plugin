# 诊断错误码目录

| 错误码 | 含义 | 用户可读解释 | 处置方向 |
|---|---|---|---|
| `MAYA_NOT_FOUND` | 找不到 Maya 或 `mayapy` | 本机没有可用的 Maya | 用户指定安装位置 |
| `ABI_MISMATCH` | Python ABI 不在支持区间 | Maya 的 Python 运行时版本不匹配 | 换受支持的 Maya 版本 |
| `MODULE_LOAD_FAILED` | 模块导入失败 | Maya 的模块路径异常 | 用户在 Maya 内核对安装 |
| `PATH_INVALID` | 路径类故障 | 路径含非 ASCII 或无法解析 | 区分编码问题与模块问题 |
| `PYTHON_NOT_FOUND` | 宿主 Python 缺失 | 系统 Python 不在 PATH | 用户安装或指定 Python |
| `OK` | 探测成功 | 环境健康 | 无需动作 |
| `DIAGNOSTICS_FAILED` | 无法归类 | 错误文本不匹配任何已知模式 | 请用户提供更完整的堆栈 |

## 前五个是公开契约

被 Skills、测试和文档同时引用。改动它们需要同步更新：
`tests/test_maya_diagnostics.py`、本文件、以及各 SKILL.md 的 Gotchas。
