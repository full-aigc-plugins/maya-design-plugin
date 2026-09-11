# Codex Maya 插件

<img src="assets/logo.png" alt="Codex Maya Logo" width="128">

> 面向 Codex 的安全、可审查 Autodesk Maya 自动化兼容基础。

[English](README.md) | [简体中文](README.zh-CN.md)

## 当前状态

仓库现已具备兼容插件基础：manifest、Marketplace 元数据、品牌资产、Legal 文档、验证脚本、测试和实施目录。Maya 业务工作流尚未实现，也未声明通过 Maya 运行兼容性验证。

## 项目定位

`codex-maya` 计划检查用户授权的 Maya 场景、选择相机和时间轴范围、生成白模或材质预览 Playblast、校验本地媒体，并恢复临时场景状态。它不上传 Dreamina；联动由 `codex-dreamina-3d` 负责。

```text
Codex -> 受控 Maya 运行器 -> mayapy / Maya batch -> Playblast -> 验证 -> 产物回执
```

## 计划边界

- 检测 Maya、`mayapy`、Python ABI、模块、插件路径、相机、时间轴和渲染设置。
- 使用 argv 调用和明确工程/输出目录范围。
- 诊断中文路径和 `ModuleNotFoundError`，但不自动安装包。
- 恢复视图面板、选择集、时间轴、渲染全局设置和临时覆盖。
- 不捆绑 Maya、编码器、供应商上传器源码或凭据。

## 文档

- [Architecture](docs/Codex-Maya-Plugin-Architecture.md) / [中文](docs/Codex-Maya-Plugin-Architecture.zh_CN.md)
- [Technical solution](docs/Codex-Maya-Plugin-Technical-Solution.md) / [中文](docs/Codex-Maya-Plugin-Technical-Solution.zh_CN.md)
- [设计规格](docs/superpowers/specs/2026-09-11-codex-maya-plugin-design.md)
- [实施计划](docs/superpowers/plans/2026-09-11-codex-maya-plugin-implementation.md)

## 许可证

Apache-2.0，见 [LICENSE](LICENSE)。
