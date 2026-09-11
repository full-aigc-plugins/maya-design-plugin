# Codex Maya Plugin

> Design-stage Codex workflows for safe, reviewable Autodesk Maya automation.

[English](README.md) | [简体中文](README.zh-CN.md)

## Status

This repository contains architecture, technical solution, and implementation plans only. No installable plugin or Maya compatibility claim exists yet.

## Purpose

`codex-maya` will inspect authorized Maya scenes, select cameras and timeline ranges, create white-model or material-aware Playblast previews, validate local media, and restore temporary scene state. It never uploads to Dreamina; `codex-dreamina-3d` owns that orchestration.

```text
Codex -> guarded Maya runner -> mayapy / Maya batch -> Playblast -> validation -> artifact receipt
```

## Planned boundaries

- Detect Maya, `mayapy`, Python ABI, modules, plug-in paths, cameras, timeline, and render settings.
- Use argv-based subprocess calls and explicit project/output scopes.
- Diagnose Chinese-path and `ModuleNotFoundError` failures without installing packages.
- Restore model panels, selection, timeline, render globals, and temporary overrides.
- Do not bundle Maya, codecs, vendor uploader source, or credentials.

## Documents

- [Architecture](docs/Codex-Maya-Plugin-Architecture.md) / [中文](docs/Codex-Maya-Plugin-Architecture.zh_CN.md)
- [Technical solution](docs/Codex-Maya-Plugin-Technical-Solution.md) / [中文](docs/Codex-Maya-Plugin-Technical-Solution.zh_CN.md)
- [Design spec](docs/superpowers/specs/2026-09-11-codex-maya-plugin-design.md)
- [Implementation plan](docs/superpowers/plans/2026-09-11-codex-maya-plugin-implementation.md)

## License

License selection is an implementation task. This design-only repository grants no license yet.
