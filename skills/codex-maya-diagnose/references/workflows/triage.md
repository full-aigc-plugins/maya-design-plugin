# 五类故障分诊流程

## 决策树

```
用户报了错
  │
  ├─ 错误文本含 "No module named" 或 "ModuleNotFoundError"？
  │     └─ 是 → MODULE_LOAD_FAILED
  │        （除非模块名就是 maya 且发生在宿主 Python —— 那是正常的）
  │
  ├─ 错误文本含 "ascii" / "non-ascii" / "unicode"？
  │     └─ 是 → PATH_INVALID
  │
  ├─ 错误文本同时含 "python" 与 "version"？
  │     └─ 是 → ABI_MISMATCH
  │
  ├─ 错误文本含 "mayapy" 或 "maya"？
  │     └─ 是 → MAYA_NOT_FOUND
  │
  └─ 都不匹配 → DIAGNOSTICS_FAILED（不硬塞）
```

## 顺序很重要

`MODULE_LOAD_FAILED` 的判定必须最先，因为 `ModuleNotFoundError` 的文本里
也可能出现 `maya` 字样（例如 `No module named 'maya.cmds'`），
如果先匹配 `MAYA_NOT_FOUND` 就会误判。

这正是 `probe_path` 里判断顺序的由来。

## 无输入时的行为

用户没有贴错误文本时，直接探测宿主环境，返回 `diagnose()` 的输出。
此时 `category` 来自运行时判断（版本、ABI），不是文本匹配。
