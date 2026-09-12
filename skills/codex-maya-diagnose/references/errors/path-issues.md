# 路径类故障

## 中文路径是**支持**的

`scripts/maya_runner.py` 用 `subprocess.run(argv_list)`，不做 shell 拼接，
因此空格与中文都不会被重新分词。文件读写统一 `encoding="utf-8"`。

测试覆盖：`tests/test_maya_runner.py::test_unicode_and_spaced_path`
（路径形如 `中文 目录 `，含中文字符**和**空格）。

## 那什么时候会报 PATH_INVALID

| 场景 | 说明 |
|---|---|
| 路径中含无法编码的字符 | 例如无效的代理对 |
| 路径长度超限 | 操作系统限制 |
| 路径指向不存在的挂载点 | 例如断开的网络盘 |

## 区分「编码问题」与「模块问题」

| 错误文本 | 类别 | 含义 |
|---|---|---|
| 含 `ascii` / `non-ascii` / `unicode` | `PATH_INVALID` | 路径编码 |
| 含 `No module named` | `MODULE_LOAD_FAILED` | 模块 |

中文路径失败**不一定**是编码问题。先看错误码再判断。

## 脱敏

诊断输出里所有绝对路径替换为 `<redacted-path>`。
相对路径原样保留。场景内节点名（`camera1`、`lambert1`）不脱敏——
它们是场景内容，不是用户隐私。
