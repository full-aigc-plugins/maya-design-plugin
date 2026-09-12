# 四个技能的能力边界对照

| 技能 | 调用 Maya | 写场景 | 产生回执 | 产生产物 | 访问网络 |
|---|---|---|---|---|---|
| `codex-maya-use` | 否 | 否 | 否 | 否 | 否 |
| `codex-maya-inspect` | 是（只读） | 否 | `scene_receipt` | 否 | 否 |
| `codex-maya-export-preview` | 是（临时改并还原） | 临时 | `artifact_receipt` | 是（MP4） | 否（仅本地网桥） |
| `codex-maya-diagnose` | 否（只探测） | 否 | 否 | 否 | 否 |

## 边界的实际意义

- 只有 `export-preview` 会产生文件产物
- 只有 `export-preview` 会临时改动场景（因此只有它需要还原机制）
- 没有任何技能会上传内容到云端
- 三个下游技能都是「可以被直接调用」的，本路由器只是辅助

## 误用检测

用户说「导出」却拿到了不含 `media_path` 的 JSON → 路由错了。
用户说「检查」却看到场景被改动 → 严重错误，立即停止。
