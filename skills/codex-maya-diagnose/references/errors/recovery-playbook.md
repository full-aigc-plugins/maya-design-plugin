# 分场景处置手册

## MAYA_NOT_FOUND

1. 确认用户是否装了 Maya（商业软件，本技能不下载）
2. 确认 `MAYA_LOCATION` 或使用 `--explicit-root`
3. 仍失败 → 说明搜索过的布局（macOS bundle / Windows bin / Linux bin）

## ABI_MISMATCH

1. 读出观察到的 Python 版本与 Maya 年份
2. 对照 [abi-matrix.md](abi-matrix.md) 说明支持区间
3. **不要**建议安装/降级 Python

## MODULE_LOAD_FAILED

1. 先排除「在宿主 Python 里 import maya」这种正常现象
2. 否则说明是 Maya 自身模块路径异常
3. 让用户在 Maya 内手动跑一次 `mayapy` 确认

## PATH_INVALID

1. 确认路径里是否真有非法字符
2. **不要**直接断言「中文路径不支持」——它是支持的
3. 若确实是编码问题，建议改用 ASCII 路径作为临时绕行

## PYTHON_NOT_FOUND

宿主 Python 缺失。说明这不是 Maya 的问题，是宿主环境的问题。
