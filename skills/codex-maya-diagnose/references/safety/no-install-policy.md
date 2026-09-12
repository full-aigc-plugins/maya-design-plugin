# 不安装策略

## 绝对禁止

| 行为 | 原因 |
|---|---|
| `pip install` | Maya 模块与 Python 包必须由用户显式安装 |
| `ensurepip` | 同上 |
| 下载二进制（ffmpeg 等） | 引入未经用户审阅的可执行文件 |
| 修改 `sys.path` | 掩盖真实安装问题，且下次会话失效 |
| 改写用户环境配置 | 越权 |

## 测试守卫

`tests/test_maya_diagnostics.py::NoInstallGuaranteeTests`：

```python
for forbidden in ("pip.main", "ensurepip", "subprocess.check_call"):
    assertNotIn(forbidden, source)

for forbidden in ("sys.path.append", "sys.path.insert", "mayapy.append"):
    assertNotIn(forbidden, source)
```

直接读源码断言，因此**任何新引入的安装调用都会让测试变红**。

## 为什么这条政策是硬性的

Maya 是商业软件，授权与环境由用户掌控。自动安装可能：
- 违反用户的许可协议
- 污染用户经过验证的生产环境
- 让故障从「可复现」变成「状态不明」

诊断技能的价值在于**把问题说清楚**，不在于替用户改环境。
