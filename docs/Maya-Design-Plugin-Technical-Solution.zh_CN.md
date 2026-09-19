# Autodesk Maya Design 插件技术方案

> **文档信息**
>
> | 字段 | 值 |
> |---|---|
> | 状态 | 离线实现已完成；真实 Maya 运行尚未验证 |
> | 范围 | Maya 集成如何构建、如何还原状态、如何验证 |
> | 读者 | 扩展或评审本插件的实现者 |
> | 运行证据 | `docs/verification/` |

## 1. 技术决策

采用 Codex Skill 层、仅 argv 的运行器，以及支持批处理检查和受控 Playblast 的 Maya Python Bridge。不复制官方 Dreamina Maya 上传器。

### 备选方案

| 备选方案 | 被否的原因 |
|---|---|
| 把官方上传器复制进本仓库 | 与供应商内部实现隐性耦合，而更新节奏由供应商掌握 |
| 用宿主 Python 直接调用 `maya.cmds` | 宿主解释器不是 Maya 的解释器，ABI 与模块路径都不可能匹配 |
| 用外部探测工具校验 MP4 | 给媒体结论引入了无法核实的依赖 |
| 通过安装依赖包修复用户的 Maya 环境 | 会改动一个受许可、由用户管理的安装 |
| 自动重试失败的渲染 | 无法修复坏环境，而且会掩盖真实失败 |

## 2. 已实现的布局

```text
.codex-plugin/plugin.json
skills/maya-*/
scripts/maya_runner.py
scripts/maya_bridge.py
scripts/media_probe.py
schemas/
tests/
```

| 路径 | 职责 |
|---|---|
| `scripts/maya_runner.py` | Maya 与 `mayapy` 发现、ABI 校验、带环境白名单的 argv 调用 |
| `scripts/maya_bridge.py` | 场景检查、Playblast、快照与还原、回执构造 |
| `scripts/maya_diagnostics.py` | 带类型且路径安全的环境诊断 |
| `scripts/media_probe.py` | 进程内的 MP4 容器与编码校验 |
| vendored Python 源码 | 官方桥接与 Playblast 模块，按校验和原样保留 |

## 3. 核心机制

- 发现 `maya`、`mayapy`、版本、Python ABI 和模块路径。
- 首先生成只读场景回执。
- 快照选择集、当前时间、播放范围、活动视图、相机、显示模式和输出设置。
- 在临时目录生成白模或材质预览 Playblast。
- 只使用已存在且获准的媒体工具转换。
- 恢复状态，并原子发布验证后的结果。

还原是"校验过"而不是"假定成立"的：每个快照字段都会在操作前后各比对一次，出现不一致时抛出 `RESTORE_UNCONFIRMED`，而不是报告成功。

## 4. 配置与状态

| 设置 | 位置 | 说明 |
|---|---|---|
| Maya 安装位置 | `MAYA_LOCATION` 环境变量 | 当 `mayapy` 不在 `PATH` 上时使用 |
| Maya Python 版本 | `MAYA_PYTHON_VERSION` 环境变量 | 在 ABI 校验时读取 |
| 环境白名单 | 由运行器强制 | 只有被批准的环境变量会传进子进程 |
| 持久状态 | 无 | 会话存在于 `mayapy` 子进程内部 |

## 5. 错误模型

`MAYA_NOT_FOUND`、`ABI_MISMATCH`、`MODULE_LOAD_FAILED`、`MAYA_PROBE_FAILED`、`SCENE_NOT_AUTHORIZED`、`CAMERA_NOT_FOUND`、`PLAYBLAST_FAILED`、`TIMEOUT`、`RESTORE_UNCONFIRMED`、`MEDIA_INVALID`、`DIAGNOSTICS_FAILED`、`PATH_INVALID`、`PYTHON_NOT_FOUND`、`UPLOAD_NOT_AUTHORIZED`。

发现与诊断类失败来自 `scripts/maya_runner.py` 与 `scripts/maya_diagnostics.py`；场景与媒体类失败来自 `scripts/maya_bridge.py` 与 `scripts/media_probe.py`。每个错误码都点名失败的前置条件，调用方无需解析文字。

## 6. 测试策略

使用 fake `maya.cmds` 做单元 TDD，用 fixture 脚本验证批处理行为，覆盖 Unicode 路径，并将真实 Maya 冒烟测试作为独立授权门禁。模块能导入不等于运行验收通过。

| 层次 | 证明 | 命令 |
|---|---|---|
| 单元 | 发现、桥接机制、还原比对、回执结构 | `python3 -m unittest discover -s tests -v` |
| 夹具 | 针对假 Maya API 的批量检查与 Playblast 行为 | 同一套件中的夹具类 |
| 路径 | Unicode 与非常规工程位置 | 同一套件中的路径类 |
| 分发 | 清单、引用与必需文件 | `python3 scripts/validate_distribution.py` |
| 真实 Maya | 实机发现、抓取与浏览器交接 | 独立授权门禁，记录于 `docs/verification/maya-runtime.md` |

## 7. 兼容性

| 方面 | 立场 |
|---|---|
| Python | 3.7 或更新，与 Maya 解释器对齐 |
| Maya | 2022 或更新 |
| 范围之外 | 2022 之前的 Maya，以及没有显式 `MAYA_LOCATION` 的 Linux 安装 |
| 验证规则 | 每个受支持的 OS/Maya/Python 组合都需要各自记录的运行测试 |

## 8. 证据映射

| 断言 | 证据 |
|---|---|
| 发现与 ABI 校验 | `scripts/maya_runner.py` |
| 还原校验 | `scripts/maya_bridge.py` |
| 媒体校验 | `scripts/media_probe.py` |
| 离线范围与缺口 | `docs/verification/offline.md` |
| 运行状态 | `docs/verification/maya-runtime.md` |
