---
name: codex-maya-export-preview
description: Reversible Playblast export from an authorized Autodesk Maya scene, producing a Codex artifact receipt with codec, fps, dimensions, SHA-256, duration, file size, and restoration status. Supports three modes - white_model for a clean clay render, material_preview to keep the scene's own materials and textures, and existing_video to register an already-rendered local clip without touching Maya at all. Every temporary Maya state change (selection, current time, playback range, camera, active panel, displayAppearance, displayTextures, renderer, image format, resolution, shader overrides) is snapshotted and restored in a finally block, even on exception, cancellation, or timeout. Use when the user asks to render a preview, make a Playblast, export a white model, generate a review clip, or hand a local video to the Dreamina pipeline. Never auto-retries a failed render, never installs codecs or packages. For a read-only inventory use codex-maya-inspect; for a failure explanation use codex-maya-diagnose.
license: Apache-2.0 — see LICENSE
---

# codex-maya-export-preview — 即梦 Maya 可恢复预览导出

从已授权的 Maya 场景导出 Playblast 预览，产出 Codex `artifact_receipt`。
**所有临时改动的场景状态都会被快照并在 `finally` 中恢复。**

## When to use / 什么时候使用

- 用户说「渲染预览」「出个白模」「Playblast」「帮我出一版 review 视频」
- 需要把 Maya 里的镜头变成可交给 `codex-dreamina-3d` 的视频产物
- 用户已经有一个本地视频，只想登记进 Codex 流水线（`existing_video` 模式）
- 需要在出图后确认「场景状态被完整还原了」

## When NOT to use / 不适用场景（不该用本技能）

- 只是想看看场景里有什么（相机 / 帧范围 / 引用）→ 用 `codex-maya-inspect`
- 导出报错了，想知道原因 → 用 `codex-maya-diagnose`
- 想上传到即梦云端、消耗付费额度 → 本技能只做本地导出，上传由 `codex-dreamina-3d` 编排
- 想修改场景本身 → 本技能只在导出期间临时改动并还原，不做永久修改

## Rules

1. **可恢复优先。** 任何写操作都必须在 `restored_maya_state` 上下文内发生；退出时逐字段比对，漂移即抛 `RESTORE_UNCONFIRMED`。
2. **一次性。** 渲染失败**绝不自动重试**。失败就是失败，把错误如实报给用户，由用户决定是否重新发起。
3. **不安装。** 缺编解码器、缺 Python 包时如实报告，由用户在 Codex 之外自行安装。不要 `pip install`。
4. **复用即梦实现。** Playblast 捕获、材质检测、ffmpeg 转换、本地网桥都复用 `scripts/jimeng_third_party/` 下的即梦官方实现，不重写。
5. **不上传。** 本技能只产生本地媒体文件与回执；本地网桥的 token 只留在进程内日志，不进入回执。
6. **相对路径。** `media_path` 是相对授权输出根的路径；绝对路径只在被脱敏的诊断里出现。
7. **帧数下限。** 即梦协议要求最少 44 帧（约 1.8 秒），少于该值在配置阶段就会被拒绝。

## Workflow

Step 1 — 确认模式：`white_model` / `material_preview` / `existing_video`。模式决定了后续所有分支。

Step 2 — 发现 Maya（`existing_video` 模式跳过）：调用 `scripts/maya_runner.py::discover_maya`。

Step 3 — 恢复性导出：在 `scripts/maya_bridge.py::restored_maya_state` 上下文内调用即梦的 `playblast.run_playblast(...)`，随后调用 `upload_bridge.start_local_bridge(...)` 启动本地网桥。

Step 4 — 组装回执：从产物文件计算 SHA-256、大小、时长，拼装成 `artifact_receipt`。网桥的 `redirect_url` 与 `resource_info_url` 写入进程内会话日志，**不进入回执**。

Step 5 — 校验媒体：用 `scripts/media_probe.py::validate_receipt` 重新探测产物并比对 SHA-256。

Step 6 — 报告：向用户给出媒体路径、时长、大小、还原状态；如需打开即梦链接，从会话日志取 `redirect_url`。

## Gotchas

1. `RESTORE_UNCONFIRMED` 意味着场景没回到导出前状态。**立刻报告，不要重试**，也不要假装成功。
2. `PLAYBLAST_FAILED` 可能发生在捕获、转换、校验、发布任一阶段，错误信息里带阶段名；如实转发阶段名。
3. `CAMERA_NOT_FOUND` 是相机名不存在，不是「没有相机」。空相机场景在 `codex-maya-inspect` 阶段就会失败。
4. `existing_video` 模式**完全不碰 Maya**，因此没有 `restored_maya_state`，`restoration_status` 恒为 `restored`。
5. 帧范围短于 44 帧会在配置阶段被拒绝，不会等到渲染完才发现——早失败是特性。
6. 网桥的 token 有 30 分钟 TTL。过期后需要重新发起导出，不要尝试延长已有 token。
7. 不要为了让导出「通过」而放宽帧数或分辨率限制。限制来自即梦协议，不是本地配置。
8. 中文路径与含空格路径都支持；`argv` 数组调用，不做 shell 拼接。
9. `-1` 之类的奇数分辨率会被向下取偶；这是 H.264 的要求，不是 bug。

## Validation

导出完成后自检清单（checklist）：

- [ ] `media_path` 指向的文件确实存在且非空
- [ ] `media_sha256` 是 64 位小写十六进制，且与文件实际摘要一致
- [ ] `media_format` 固定为 `video/mp4`
- [ ] `frame_rate` > 0，`width`/`height` ≥ 1，`duration_seconds` ≥ 0
- [ ] `restoration_status` ∈ {`restored`, `partial`, `unconfirmed`}
- [ ] `scene_id` 与检查阶段产出的 `scene_id` **完全一致**
- [ ] 回执中**不含** `redirect_url` / `resource_info_url`
- [ ] **verify** 退出上下文后场景状态与进入前逐字段相等

## Safety declaration / 安全声明

本技能**不访问外部网络**（本地网桥只监听 `127.0.0.1`）、**不收集用户数据**、
**不上传场景内容或视频**、**不安装任何软件**、**不记录绝对路径**。
它只在用户授权的工程范围内读写本地文件，所有临时场景改动都会还原。
本地网桥的访问 token 仅存在于当前进程内存中，不落盘、不进入回执。

## References

需要更细的执行细节时加载以下文件：

- [references/workflows/pipeline.md](references/workflows/pipeline.md) — 六步导出流水线详解
- [references/workflows/modes.md](references/workflows/modes.md) — 三种模式的差异与选择
- [references/workflows/restoration.md](references/workflows/restoration.md) — 状态快照与还原机制
- [references/workflows/media-validation.md](references/workflows/media-validation.md) — 媒体验证与 SHA-256 契约
- [references/workflows/local-bridge.md](references/workflows/local-bridge.md) — 本地网桥与 token 生命周期
- [references/errors/error-catalog.md](references/errors/error-catalog.md) — 全部错误码
- [references/errors/retry-policy.md](references/errors/retry-policy.md) — 为什么绝不自动重试
- [references/errors/restoration-failures.md](references/errors/restoration-failures.md) — 还原失败处置
- [references/schemas/artifact-receipt-fields.md](references/schemas/artifact-receipt-fields.md) — 回执字段全表
- [references/safety/vendor-integration.md](references/safety/vendor-integration.md) — 即梦源码复用边界与校验和
