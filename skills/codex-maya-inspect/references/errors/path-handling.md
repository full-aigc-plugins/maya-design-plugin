# 路径处理与脱敏规则

## 输入侧

`scene_path` 必须是**相对授权工程根目录**的路径，例如 `scenes/hero.ma`。

绝对路径在两种情况下出现：

1. 用户直接给了绝对路径 → 接受，但回执里的 `scene_path` 仍写用户给的字符串；
   仅在**诊断输出**中脱敏。
2. 诊断信息里出现绝对路径 → 一律替换为 `<redacted-path>`。

## 中文路径

中文路径是**支持**的。实现要点：

- `scripts/maya_runner.py` 用 `subprocess.run(argv_list)`，不做 shell 拼接，
  因此空格和中文都不会被重新分词。
- 文件读写统一 `encoding="utf-8"`。
- 测试 `tests/test_maya_runner.py::test_unicode_and_spaced_path` 覆盖了
  `中文 目录 ` 这种带空格的中文路径。

如果用户在中文路径上遇到 `ModuleNotFoundError`，那不是路径编码问题，
而是 Maya 模块搜索路径问题——交给 `codex-maya-diagnose`。

## 脱敏实现

```python
def _redact(value: str) -> str:
    if not value:
        return value
    return "<redacted-path>" if os.path.isabs(value) else value
```

对 `diagnostics_for(receipt)` 里的字符串、字符串列表、字符串字典值递归应用。

## 明确不做的事

- 不把绝对路径写进任何回执字段
- 不把环境变量内容写进诊断（只写类别和观察到的版本号）
- 不把家目录展开成绝对路径后再输出

## 为什么这条规则重要

场景路径常常包含项目名、客户名或艺术家姓名。这些信息如果进入
`codex-dreamina-3d` 的编排日志，就构成了不必要的信息扩散。
脱敏在最靠近产生点的位置做，而不是依赖下游过滤。
