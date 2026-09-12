# 三步上手

## 第一步：看场景

```
用 codex-maya-inspect 检查 scenes/hero.ma，告诉我相机和帧范围
```

拿到 `scene_receipt`，记下 `scene_id`。

## 第二步：出预览

```
用 codex-maya-export-preview 出白模，scene_id 用上一步的
```

拿到 `artifact_receipt`，里面有 `media_path` 和 `media_sha256`。

## 第三步（可选）：排障

任何一步失败：

```
用 codex-maya-diagnose 分析这个错误：<粘贴报错>
```

拿到类别与脱敏诊断。

## 三个可直接复制的开场白

1. 「用 codex-maya-inspect 检查 `<场景路径>`」
2. 「用 codex-maya-export-preview 出 `<模式>` 预览，相机 `<相机名>`，帧范围 `<起>`–`<止>`」
3. 「用 codex-maya-diagnose 分析：`<报错文本>`」
