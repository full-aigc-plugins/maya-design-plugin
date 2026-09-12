# Maya 版本与 Python ABI 对照

| Maya 版本 | Python | 支持状态 |
|---|---|---|
| 2022 | 3.7 | 支持 |
| 2023 | 3.7 | 支持 |
| 2024 | 3.7 | 支持 |
| 2020 及更早 | 2.7 / 3.6 | **不支持**（Python 2 运行时） |
| 2025+ | 3.11+ | 未验证 |

## 判定逻辑

```python
if maya_year < 2022:        → ABI_MISMATCH
elif python_version != 3.7: → ABI_MISMATCH
else:                       → OK
```

## 关键约束

宿主 Python 与 Maya Python 是**两个独立运行时**。
宿主跑 3.13 而 Maya 跑 3.7 是**正常且预期**的。

因此：

- **不要**因为 ABI 不匹配就建议改宿主 Python
- **不要**建议在宿主里 `pip install maya`
- `maya` 模块只存在于 Maya 自带的 Python 中

## 为什么只支持 3.7

Maya 2022–2024 都基于 Python 3.7。这是即梦官方插件（`maya_runner` 里
`SUPPORTED_PYTHON_VERSION = (3, 7)`）声明的区间，Codex 侧沿用。
