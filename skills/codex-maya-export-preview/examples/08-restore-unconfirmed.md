# 示例 8：还原未确认

**用户说：** 「导出完我的场景好像不太对。」

**症状：** `RESTORE_UNCONFIRMED: restoration mismatch on field 'current_time'`

**处置：**
1. 停止一切 Maya 调用
2. 如实报告字段名
3. **不重试**
4. 让用户决定：手动检查 / 撤销到保存点 / 忽略
