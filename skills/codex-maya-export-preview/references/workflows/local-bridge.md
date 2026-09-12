# 本地网桥与 token 生命周期

## 网桥做什么

在 `127.0.0.1` 上随机端口起一个 HTTP 服务，向即梦 Web 端提供：

- `GET /resouce_info?token=...` → `{file_url, prompt}`
- `GET /file?token=...` → 流式返回 MP4

即梦 Web 打开带 `thirdparty_id` 的链接后，回连本机取视频。

## token 生命周期

| 事件 | 行为 |
|---|---|
| 创建 | `secrets.token_urlsafe(24)` 随机 token |
| TTL | 默认 30 分钟，到期后返回 410 并关闭 |
| 首次下载完成 | 60 秒后关闭 |
| token 不匹配 | 403 `INVALID_TOKEN` |

## Codex 侧的边界

**`redirect_url` 与 `resource_info_url` 绝不进入 `artifact_receipt`。**

原因：它们内嵌 token，属于会话凭据。进入回执就会流入
`codex-dreamina-3d` 的编排日志，构成凭据扩散。

处理方式：`maya_bridge._record_bridge_session()` 把完整网桥响应写入
`sys.modules` 下的进程内日志。`mayapy` 子进程退出即消失，不落盘。
需要打开链接时用 `consume_bridge_session_log()` 取出并清空。

## CORS 白名单

即梦实现只允许来自 `*.jianying.com`、`*.capcut.com` 与 localhost 的跨域请求。
这是即梦上游的行为，Codex 侧不改动。
