# 脱敏策略

## 脱敏对象

绝对路径。包括：

- 场景绝对路径
- Maya 安装路径
- 模块搜索路径

## 脱敏方式

替换为字面量 `<redacted-path>`。

## 不做脱敏的对象

- 相对路径（`scenes/hero.ma` 原样保留）
- 场景内部节点名（`camera1`、`lambert1`）——这些是场景内容，不是用户隐私
- Maya 版本号、Python 版本号

## 环境变量

诊断报告**只报告类别和观察到的版本号**，绝不输出环境变量的值。
`tests/test_maya_diagnostics.py::DiagnosticsRedactionTests` 覆盖了这条。
