# 确定性输出规则

## 为什么要求确定性

`codex-dreamina-3d` 会把 `scene_receipt` 与后续的 `artifact_receipt` 做关联比对。
如果同一场景两次检查产生不同回执，关联就会失效，用户会看到「同一个场景」
却匹配不上的诡异结果。

## scene_id 的派生

```
scene_id = uuid4_shape(sha256(str(scene_path)))
```

具体步骤：

1. 对场景路径字符串做 SHA-256，得到 32 字节摘要。
2. 取前 16 字节，把第 7 字节的高 4 位强制为 `0b0100`（UUID v4 版本位）。
3. 把第 9 字节的高 2 位强制为 `0b10`（RFC 4122 variant 位）。
4. 按 8-4-4-4-12 分组格式化为字符串。

因此：同一路径 → 同一 `scene_id`；不同路径 → 不同 `scene_id`。
路径变化（例如从 `scenes/hero.ma` 改成 `scenes/boss.ma`）会换 ID，
这是预期行为。

## JSON 序列化的字节稳定性

`maya_bridge.to_json()` 使用固定参数：

```python
json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

- `sort_keys=True` — 键顺序固定，不受字典插入顺序影响
- `separators=(",", ":")` — 去掉空白，压缩但可读
- `ensure_ascii=False` — 中文不被转义，保证跨平台字节一致

## 测试如何验证

`tests/test_scene_inspection.py::DeterminismTests` 用两个独立的 fake 实例
跑两次检查，断言 `to_json()` 的输出完全相等。这比断言「字段相等」更强，
因为它同时覆盖了键顺序和空白。

## 已知的非确定性来源（已被消除）

| 来源 | 处理方式 |
|---|---|
| `uuid.uuid4()` 随机 ID | 改为 SHA-256 派生 |
| 字典插入顺序 | `sort_keys=True` |
| 相机列表顺序 | 固定取 `[0]`，不排序也不随机 |
| 浮点格式化 | 帧范围与分辨率统一 `int()` 截断 |
