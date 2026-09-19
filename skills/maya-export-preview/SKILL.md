---
name: maya-export-preview
description: Reversible Playblast export from an authorized Autodesk Maya scene, producing a Codex artifact receipt with codec, fps, dimensions, SHA-256, duration, file size, and restoration status. Supports three modes - white_model for a clean clay render, material_preview to keep the scene's own materials and textures, and existing_video to register an already-rendered local clip without touching Maya at all. Every temporary Maya state change (selection, current time, playback range, camera, active panel, displayAppearance, displayTextures, renderer, image format, resolution) is snapshotted and restored in a finally block, even on exception, cancellation, or timeout. Use when the user asks to render a preview, make a Playblast, export a white model, generate a review clip, or hand a local video to the Dreamina pipeline. Never auto-retries a failed render, never installs codecs or packages. For a read-only inventory use maya-inspect; for a failure explanation use maya-diagnose.
license: Apache-2.0 — see LICENSE
---

# maya-export-preview — 即梦 Maya 可恢复预览导出

从已授权的 Maya 场景导出 Playblast 预览，产出 Codex `artifact_receipt`，并在用户明确
授权后通过官方本地桥接返回即梦链接。
**所有临时改动的场景状态都会被快照并在 `finally` 中恢复。**

## When to use / 什么时候使用

- 用户说「渲染预览」「出个白模」「Playblast」「帮我出一版 review 视频」
- 需要把 Maya 镜头渲染成预览并生成即梦链接
- 用户已经有一个本地视频，需要直接生成即梦链接（`existing_video` 模式）
- 需要在出图后确认「场景状态被完整还原了」

## When NOT to use / 不适用场景（不该用本技能）

- 只是想看看场景里有什么（相机 / 帧范围 / 引用）→ 用 `maya-inspect`
- 导出报错了，想知道原因 → 用 `maya-diagnose`
- 想自动登录即梦或执行付费生成 → 本技能只生成链接，账号登录和生成确认由用户完成
- 想修改场景本身 → 本技能只在导出期间临时改动并还原，不做永久修改

## Rules

1. **可恢复优先。** 任何写操作都必须在 `restored_maya_state` 上下文内发生；退出时逐字段比对，漂移即抛 `RESTORE_UNCONFIRMED`。
2. **一次性。** 渲染失败**绝不自动重试**。失败就是失败，把错误如实报给用户，由用户决定是否重新发起。
3. **不安装。** 缺编解码器、缺 Python 包时如实报告，由用户在 Codex 之外自行安装。不要 `pip install`。
4. **复用即梦实现。** Playblast 捕获、材质检测、ffmpeg 转换、本地网桥都复用 `scripts/jimeng_third_party/` 下的即梦官方实现，不重写。
5. **链接与回执分离。** 临时 token 不进入稳定回执；授权调用通过独立 `jimeng_link` 块返回链接。
6. **相对路径。** `media_path` 是相对授权输出根的路径；绝对路径只在被脱敏的诊断里出现。
7. **帧数下限。** 即梦协议要求最少 44 帧（约 1.8 秒），少于该值在配置阶段就会被拒绝。

## Workflow

真正的入口只有一条命令。**不要**自己拼 `mayapy` 命令行、不要从宿主直接调 `maya_bridge` 的函数——它只在 Maya 内部有效。

Step 1 — 确认模式：`white_model` / `material_preview` / `existing_video`，然后写一个 request JSON。

Step 2 — 运行导出（driver 自己负责发现 Maya、argv 传参、超时与终止）：

```bash
# 需要即梦链接时用 jimeng-flow（必须显式授权）
python3 scripts/maya_runner.py jimeng-flow --request <request.json>

# 只要本地产物与回执时用 export
python3 scripts/maya_runner.py export --request <request.json>
```

request JSON 形如：

```json
{"mode": "white_model", "camera": "camera1",
 "start_frame": 1, "end_frame": 120, "frame_rate": 24,
 "scene_id": "<上一步 inspect 的 scene_id>",
 "authorize_upload": true}
```

`existing_video` 模式把 `video_path` 换成已渲染的本地文件，其余字段不变。

Step 3 — 读取 stdout：`{"artifact_receipt": {...}, "jimeng_link": {...}}`。
`artifact_receipt` **不含** token；`jimeng_link` 只在本次进程内有效。
失败时 driver 以非零退出并把 `{"code": ..., "message": ...}` 写到 stderr——**按 code 分支，不要解析自然语言**。

Step 4 — 用 `scripts/media_probe.py::validate_receipt` 复核产物的 SHA-256 与编码参数。

Step 5 — 报告：媒体路径、时长、大小、还原状态，以及（若已授权）即梦链接。
链接有时效（默认 30 分钟），过期后需重新运行一次导出，**不要**尝试延长已有 token。

### 底层调用链（排障时才需要了解）

```
python3 scripts/maya_runner.py jimeng-flow --request <req.json>   ← 你调用的
  └─ maya_runner.discover_maya(...)                               ← 发现 mayapy
  └─ maya_runner.run_request(...)                                 ← argv 启动子进程
       └─ mayapy scripts/maya_request.py <req> <resp>             ← Maya 内部入口
            └─ maya_bridge.run_jimeng_flow(maya.cmds, ...)        ← 授权 + 编排
                 └─ restored_maya_state(...)                      ← 外层快照/校验
                      └─ 即梦 playblast.run_playblast(...)        ← 内层还原
                      └─ 即梦 upload_bridge.start_local_bridge()  ← 本地网桥
```

`scripts/maya_runner.py` 是宿主侧 driver，`scripts/maya_request.py` 是 Maya 内部 runner。
`scripts/maya_bridge.py` 是纯库，直接运行它会以退出码 2 拒绝并提示正确的入口。

## Gotchas

1. `RESTORE_UNCONFIRMED` 意味着场景没回到导出前状态。**立刻报告，不要重试**，也不要假装成功。
2. `PLAYBLAST_FAILED` 可能发生在捕获、转换、校验、发布任一阶段，错误信息里带阶段名；如实转发阶段名。
3. `CAMERA_NOT_FOUND` 是相机名不存在，不是「没有相机」。空相机场景在 `maya-inspect` 阶段就会失败。
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

本技能会按官方实现获取即梦 DCC 配置并生成即梦网页链接；视频由即梦网页通过
`127.0.0.1` 临时桥接读取，不发布为公网文件。技能**不收集账号凭据**、**不安装任何软件**。
它只在用户授权的工程范围内读写本地文件，所有临时场景改动都会还原。
本地网桥的访问 token 仅存在于当前进程内存中，不落盘、不进入回执。

## References

需要更细的执行细节时按需加载：

- [决策指南](references/decisions/decision-guide.md)
- [失败矩阵](references/operations/failure-matrix.md)
- [交付验证清单](references/operations/validation-checklist.md)

<!-- QUALITY_CONTRACT_START -->
## 什么时候使用

✅ 适用：

1. 用户明确要从已授权 Maya 场景导出可验证且可恢复的 Playblast 预览。
2. 已提供或可安全取得必要上下文，需要得到可验证的 `maya-artifact-receipt`。
3. 需要按最小权限、可回滚方式执行，并保留审计证据。

⚠️ 先澄清：

1. 目标环境、授权边界或成功标准缺失时，先给出只读假设方案并列出缺失项。
2. 涉及生产环境变更时，先确认备份、维护窗口和回滚路径。
3. 输入可能含敏感信息时，只引用字段名和脱敏片段，不复制完整凭据。

❌ 不该用：

1. 最终离线渲染、未经确认的上传或自动重试可能重复产生副作用的导出。
2. 用户只要概念解释且没有执行或交付需求。
3. 需要绕过鉴权、证书校验、人工确认或其他安全控制的请求。

## Workflow

Step 1：确认目标、环境、授权范围和不可变约束；信息不足时先产出带假设的只读版本。

Step 2：盘点现状与依赖，只读取必要数据，不记录令牌、密码、Cookie 或完整个人数据。

Step 3：选择最小影响路径，将高风险动作、外部网络调用和可逆步骤明确标注。

Step 4：生成或执行 `maya-artifact-receipt`，每一步都绑定输入、预期输出与失败条件。

Step 5：校验结构、事实来源和目标状态；禁止根据缺失证据编造成功结论。

Step 6：失败时停止扩大影响，输出已完成步骤、失败证据、恢复点和下一次安全重试条件。

Step 7：交付摘要、验证证据、剩余风险与后续动作；生产变更必须说明回滚是否已验证。

## Rules

- 默认只读；写操作、高危操作和付费调用必须获得与该动作匹配的明确授权。
- 本技能不收集、不存储、不上传用户凭据；日志和报告不得包含完整 token、密码或密钥。
- 不关闭 TLS 校验，不执行来源不明脚本，不使用管道下载后直接执行。
- 只把真实执行结果写成“已完成”；计划、示例和推断必须显式标注。
- 优先幂等操作；无法幂等时先提供预演、备份和回滚点。

## Validation checklist

- [ ] 目标、环境与授权范围均已写明。
- [ ] `视频文件、SHA-256、帧范围、分辨率、模式和场景状态还原证据完整` 已由可复现证据验证。
- [ ] 敏感数据已脱敏，输出中没有完整凭据。
- [ ] 失败与超时路径已覆盖，未出现无限重试。
- [ ] 变更类任务具有备份或回滚说明。
- [ ] 最终结论区分事实、推断和未验证项。

## Gotchas

1. **授权不等于可达**：有权限但网络、证书或白名单不满足时，仍应停止并报告连接证据。
2. **成功码不等于业务成功**：必须检查 `视频文件、SHA-256、帧范围、分辨率、模式和场景状态还原证据完整`，不能只看命令退出码或 HTTP 200。
3. **重试不等于恢复**：对鉴权失败、参数错误和安全拒绝不得盲目重试。
4. **示例不等于现状**：模板值与占位符不能写成真实环境数据。
5. **输出不等于交付**：还需完成结构校验、风险说明和可重复验证。
6. **跨环境不可照搬**：操作系统、版本、区域和宿主能力不同时必须重新确认参数。

## 渐进式资料

- 做路径选择前读取 `references/decisions/decision-guide.md`。
- 遇到异常、超时或部分成功时读取 `references/operations/failure-matrix.md`。
- 完成交付前读取 `references/operations/validation-checklist.md`。
- 需要可复制输入时，按顺序参考 `examples/basic.md`、`examples/failure.md`、`examples/advanced.md`。
<!-- QUALITY_CONTRACT_END -->
