# 故障处置手册

## MAYA_NOT_FOUND

1. 确认用户是否装了 Maya（商业软件，本技能不下载）
2. 确认 `MAYA_LOCATION` 或搜索路径
3. 仍失败 → 交给 `codex-maya-diagnose`

## ABI_MISMATCH

1. 读出观察到的 Python 版本
2. 说明支持区间（Maya 2022–2024 = Python 3.7）
3. **不要**建议安装/降级 Python

## MODULE_LOAD_FAILED

1. 说明是 Maya 自身模块路径异常
2. 让用户在 Maya 里手动跑一次 `mayapy` 确认安装完整
3. **不要**尝试 `pip install`

## SCENE_NOT_AUTHORIZED

按三种子因分别处置：路径未授权 / 无相机 / 帧范围倒置。
**不要**自动「修复」场景。
