# Codex Maya 插件

<img src="assets/logo.png" alt="Codex Maya Logo" width="128">

> 面向 Codex 的安全、可审查 Autodesk Maya 自动化兼容基础。

[English](README.md) | [简体中文](README.zh-CN.md)

## 当前状态

仓库已完成离线函数级集成：Codex 直接复用即梦官方 Maya 插件的 Playblast、ffmpeg
转换和本地桥接，为相机渲染或已有视频返回即梦链接。真实 Maya 驱动与运行兼容性
仍未验收，不能由离线测试推断。

## 项目定位

`codex-maya` 检查用户授权的 Maya 场景、生成可恢复的白模或材质 Playblast，并复用
官方 `upload_bridge.start_local_bridge()` 生成即梦链接。稳定回执不保存临时 token，
链接只在用户明确授权的当次响应中返回。

```text
Codex -> 受控 Maya 运行器 -> mayapy / Maya batch -> Playblast -> 验证 -> 产物回执
```

## 计划边界

- 检测 Maya、`mayapy`、Python ABI、模块、插件路径、相机、时间轴和渲染设置。
- 使用 argv 调用和明确工程/输出目录范围。
- 诊断中文路径和 `ModuleNotFoundError`，但不自动安装包。
- 恢复视图面板、选择集、时间轴、渲染全局设置和临时覆盖。
- 不捆绑 Maya、编码器或凭据；即梦官方 Python 源码按校验和原样 vendoring。

## 文档

- [安装、授权与使用指南](docs/getting-started.zh-CN.md)
- [Architecture](docs/Codex-Maya-Plugin-Architecture.md) / [中文](docs/Codex-Maya-Plugin-Architecture.zh_CN.md)
- [Technical solution](docs/Codex-Maya-Plugin-Technical-Solution.md) / [中文](docs/Codex-Maya-Plugin-Technical-Solution.zh_CN.md)
- [设计规格](docs/superpowers/specs/2026-09-11-codex-maya-plugin-design.md)
- [实施计划](docs/superpowers/plans/2026-09-11-codex-maya-plugin-implementation.md)

## 许可证

Apache-2.0，见 [LICENSE](LICENSE)。
