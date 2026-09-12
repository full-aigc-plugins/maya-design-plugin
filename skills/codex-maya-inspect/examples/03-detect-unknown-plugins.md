# 示例 3：检测未知插件

**用户说：** 「这个场景能不能直接导出？会不会缺插件？」

**执行：** `codex-maya-inspect`

**输出要点：**
- 读取 `cmds.ls(type="unknownPlugin")`
- 非空 → `inspection_status = degraded`，并把插件名放进 `unknown_plugins`
- `degraded` 不是错误，是「导出可能失败」的提示

**后续建议：** 提示用户先在 Maya 里解决缺失插件，再走导出。
