# Codex Maya Plugin

<img src="assets/logo.png" alt="Codex Maya logo" width="128">

> Compatibility foundation for safe, reviewable Autodesk Maya automation in Codex.

[English](README.md) | [简体中文](README.zh-CN.md)

## Status and version

The repository now has an offline function-level integration that reuses the official Jimeng Maya Playblast, ffmpeg, and loopback-bridge modules for both camera and existing-video links. The executable real-Maya driver and runtime compatibility are not yet verified.

## Quick start

```bash
codex plugin marketplace add partme-ai/codex-maya-plugin --ref main
codex plugin add codex-maya@partme-ai-maya
```

Restart Codex or the ChatGPT desktop app, open a new task, and ask Codex to inspect a Maya scene and produce a Playblast preview. The plugin never uploads to Dreamina; `codex-dreamina-3d` owns that orchestration.

## What you can build

`codex-maya` inspects authorized Maya scenes, creates reversible previews, and returns an ephemeral Jimeng link after explicit upload authorization. Stable artifact receipts remain free of local-bridge tokens.

```text
Codex -> guarded Maya runner -> mayapy / Maya batch -> Playblast -> validation -> artifact receipt
```

The plugin never bundles Maya, codecs, vendor Python source, or credentials; vendored Python source is checksummed verbatim.

## Boundaries and contracts

- Detect Maya, `mayapy`, Python ABI, modules, plug-in paths, cameras, timeline, and render settings.
- Use argv-based subprocess calls and explicit project/output scopes.
- Diagnose Chinese-path and `ModuleNotFoundError` failures without installing packages.
- Restore model panels, selection, timeline, render globals, and temporary overrides.
- Do not bundle Maya, codecs, or credentials; vendor Python source is checksummed verbatim.

## Documentation

- [Chinese installation, authorization, and usage guide](docs/getting-started.zh-CN.md)
- [Architecture](docs/Codex-Maya-Plugin-Architecture.md) · [架构文档](docs/Codex-Maya-Plugin-Architecture.zh_CN.md)
- [Technical solution](docs/Codex-Maya-Plugin-Technical-Solution.md) · [技术方案](docs/Codex-Maya-Plugin-Technical-Solution.zh_CN.md)
- [Design spec](docs/superpowers/specs/2026-09-11-codex-maya-plugin-design.md)
- [Implementation plan](docs/superpowers/plans/2026-09-11-codex-maya-plugin-implementation.md)

## License

Apache-2.0 — see [LICENSE](LICENSE).
