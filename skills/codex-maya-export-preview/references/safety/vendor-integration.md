# 即梦源码复用边界

## 复用什么

`scripts/jimeng_third_party/jimeng_maya_uploader/` 下的即梦官方实现，**逐字节原样**：

| 模块 | 职责 |
|---|---|
| `playblast.py` | 视口状态快照/还原、材质检测、Playblast 调用、ffmpeg 转换 |
| `upload_bridge.py` | ffmpeg 候选链、本地 HTTP 网桥、文件大小校验 |
| `dcc_config.py` | 即梦 DCC 协议配置获取、分辨率/帧数/大小校验 |
| `settings.py` | 用户配置读写、默认输出目录 |
| `variant.py` | 区域/语言变体（cn / mac / zh_cn） |
| `ui.py` / `maya_qt.py` | Qt 面板（Codex 路径不使用） |
| `startup.py` | Maya 启动自动加载（Codex 路径不使用） |

## 不复用什么

- **Qt UI**：Codex 通过 Skills 驱动，不需要面板。
- **startup hook**：会修改用户 Maya 启动配置，Codex 不碰。

## 完整性锁定

`maya_bridge.JIMENG_VENDOR_CHECKSUM` 记录了整棵子树的 SHA-256
（路径 + 内容的滚动摘要）。`verify_vendor_checksum()` 在每次导出前校验。

`tests/test_playblast.py::VendorIntegrityTests` 与
`tests/test_distribution_extended.py::VendorSubtreeTests` 各测一遍。

## 升级上游的步骤

1. 替换 `scripts/jimeng_third_party/jimeng_maya_uploader/` 下的文件
2. 重新计算校验和并更新 `JIMENG_VENDOR_CHECKSUM`
3. 更新 `FFMPEG_VERSION.txt`
4. 跑全量测试

**不要**在子目录内直接改代码——校验和会让测试立刻变红。
