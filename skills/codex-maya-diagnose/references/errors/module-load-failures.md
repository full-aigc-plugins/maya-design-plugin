# 模块加载失败细分

## 三种子因

| 子因 | 症状 | 区分方式 |
|---|---|---|
| 模块真的不存在 | `No module named 'foo'` | 模块名不是 `maya*` |
| 在错误的解释器里导入 | 宿主 Python 报 `No module named 'maya'` | 模块名是 `maya` 且跑在宿主 |
| 模块路径被污染 | `mayapy` 的 `sys.path` 探测非零退出 | `MODULE_LOAD_FAILED` 且无 `No module named` |

## 第二种是**正常现象**

在宿主的 Python 3.13 里跑 `import maya` 报 `No module named 'maya'`
**不是故障**——`maya` 只存在于 Maya 自带的 Python 3.7 里。

用户看到这个报错时，正确回应是解释这一点，而不是判定安装损坏。

## 第三种才是真故障

`_resolve_module_paths` 用
`mayapy -c "import sys, json; print(json.dumps(sys.path))"` 探测模块路径。
若非零退出或输出不是 JSON，说明 Maya 自身的模块路径异常，
这需要用户在 Maya 内核对安装完整性。

## 不要做的事

- **不要** `pip install` 缺失模块。Maya 模块必须通过 Maya 的安装/模块机制提供。
- **不要**往 `sys.path` 里塞目录来「修好」它。那会掩盖真实的安装问题，
  且在下一次会话里失效。
