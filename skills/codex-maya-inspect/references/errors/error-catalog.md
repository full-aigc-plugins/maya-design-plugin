# 错误码目录（场景检查）

| 错误码 | 触发条件 | 用户可读解释 | 处置建议 |
|---|---|---|---|
| `MAYA_NOT_FOUND` | 找不到 `mayapy`，或 `MAYA_LOCATION` 未设置且搜索路径为空 | 本机没有可用的 Maya | 让用户确认 Maya 安装位置，用 `--explicit-root` 或 `MAYA_LOCATION` 指定 |
| `ABI_MISMATCH` | `mayapy` 的 Python 版本不是 3.7（Maya 2022–2024），或 Maya 年份 < 2022 | Maya 的 Python 运行时不在支持区间 | **不要安装 Python**。提示用户使用受支持的 Maya 版本 |
| `MODULE_LOAD_FAILED` | `mayapy -c "import sys, json; print(json.dumps(sys.path))"` 非零退出或输出非 JSON | Maya 自带的 Python 模块路径异常 | 让用户在 Maya 里手动跑一次 `mayapy` 确认安装完整 |
| `SCENE_NOT_AUTHORIZED` | 场景路径未授权、场景无相机、或帧范围 start > end | 场景不满足可检查前提 | 分别提示：换授权路径 / 场景里加相机 / 修正播放范围 |
| `PATH_INVALID` | 路径含非法字符或无法解析 | 路径无法读取 | 用 `codex-maya-diagnose` 细化；中文路径本身是支持的 |

## 不该做的事

- **不要**因为 `MAYA_NOT_FOUND` 就去 `pip install maya` 或下载 Maya。Maya 是商业软件，必须由用户自行安装。
- **不要**因为 `ABI_MISMATCH` 就去改宿主 Python 版本。宿主与 Maya 是两个独立运行时。
- **不要**在 `SCENE_NOT_AUTHORIZED` 时「自己修复」场景（加相机、改范围）。检查的职责是报告，不是修复。

## 错误码的稳定契约

这些字符串是稳定的公开契约，会被 Skills、测试和 `codex-dreamina-3d` 同时引用。
改动它们属于破坏性变更，必须同步更新 `tests/test_scene_inspection.py`
和本文件。
