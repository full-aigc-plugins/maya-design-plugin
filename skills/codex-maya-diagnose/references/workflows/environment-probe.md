# 宿主环境探测

## 探测什么

| 项 | 来源 | 是否脱敏 |
|---|---|---|
| Python 实现 | `platform.python_implementation()` | 否 |
| Python 版本 | `sys.version_info[:3]` | 否 |
| ABI flags | `sys.abiflags` | 否 |
| Python 可执行文件 | `sys.executable` | **是** |
| 平台 | `platform.platform()` | 否 |

## Maya 运行时探测

通过 `maya_runner.discover_maya(None, "")`，返回：

- `mayapy` 路径（**脱敏**）
- Maya 版本（原始值，如 `2024`）
- Python 版本（如 `3.7`）
- 模块路径**数量**（不是内容）

## 为什么模块路径只报数量

模块路径列表里每一项都可能含用户名或项目名。逐条脱敏后列表本身信息量很低，
而**数量**足以回答关键问题：「模块路径是否为空？」

例如 `module_path_count: 0` 直接指向安装损坏，
`module_path_count: 12` 说明路径正常，问题在别处。

## 探测的副作用

**零副作用。** 只读 `sys` / `platform` 属性，不写任何东西，不改 `sys.path`，
不导入 Maya 模块。
