# 只读保证清单

| 保证 | 实现方式 | 测试 |
|---|---|---|
| 不改选择集 | 前后比对 `ls_sl()` | `NoMutationTests.test_selection_is_not_changed` |
| 不改当前帧 | 前后比对 `currentTime()` | `NoMutationTests.test_current_time_is_not_changed` |
| 不加载插件 | 前后比对已加载插件集合 | `NoMutationTests.test_no_plugin_is_loaded` |
| 不调用任何写接口 | fake 里写接口直接抛异常 | `NoMutationTests.test_attempted_select_raises` |

## 测试机制

`tests/fakes/fake_maya_cmds.py` 里的 `FakeCmds` 把 `select` / `loadPlugin`
等写接口实现为抛 `MutationForbiddenError`。因此**任何写操作都会让测试变红**，
不是靠代码审查发现。
