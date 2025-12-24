# 数据库开发规范文档

## 概述

本文档定义了交易系统数据库的开发和维护规范，确保数据库操作的一致性、性能和可维护性。所有涉及数据库修改的功能开发都必须遵循本规范。

## 数据库文件管理

### 主数据库
- **文件名**: `trading_bot.db`
- **位置**: 项目根目录
- **用途**: 存储所有交易数据、信号、持仓快照等核心数据

### 备份策略
- **自动备份**: 每次重大修改前必须备份
- **命名规范**: `trading_bot_backup_YYYYMMDD_HHMMSS.db`
- **保留策略**: 保留最近7天的备份，自动清理旧备份
- **备份命令**: `cp trading_bot.db trading_bot_backup_$(date +%Y%m%d_%H%M%S).db`

### 禁止事项
- ❌ 不要创建多个主数据库文件
- ❌ 不要使用未在config.py中定义的数据库文件
- ❌ 不要直接删除主数据库文件

## 数据库表设计规范

### 表命名规范
- 使用小写字母和下划线
- 使用复数形式（如 `trades`, `signals`）
- 名称要清晰表达表的用途

### 字段命名规范
- 使用小写字母和下划线
- 主键统一命名为 `id`
- 时间戳字段统一命名为 `created_at`
- 外键字段使用 `{表名}_id` 格式

### 必需字段
每个表必须包含以下字段：
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### 字段类型规范
| 数据类型 | SQLite类型 | 说明 |
|---------|-----------|------|
| 整数 | INTEGER | 用于ID、计数等 |
| 小数 | REAL | 用于价格、数量、百分比等 |
| 文本 | TEXT | 用于字符串、JSON等 |
| 时间 | TIMESTAMP | 用于时间记录 |

## 索引规范

### 必须创建索引的情况
1. **时间字段**: 所有 `created_at` 字段必须有索引
2. **查询字段**: 经常用于WHERE条件的字段
3. **关联字段**: 用于JOIN的外键字段
4. **排序字段**: 经常用于ORDER BY的字段

### 索引命名规范
```
idx_{表名}_{字段名}
```

示例：
```sql
CREATE INDEX idx_trades_created_at ON trades(created_at);
CREATE INDEX idx_trades_strategy ON trades(strategy);
```

### 复合索引
对于经常一起查询的字段，创建复合索引：
```sql
CREATE INDEX idx_trades_symbol_side ON trades(symbol, side);
```

## 数据库操作规范

### 连接管理
```python
# ✅ 正确：使用统一的数据库类
from logger_utils import db
db.log_trade(...)

# ❌ 错误：直接创建连接
conn = sqlite3.connect('trading_bot.db')
```

### 事务处理
```python
# ✅ 正确：使用事务
conn = self._get_conn()
try:
    cursor = conn.cursor()
    cursor.execute("INSERT ...")
    cursor.execute("UPDATE ...")
    conn.commit()
finally:
    conn.close()

# ❌ 错误：不使用事务
cursor.execute("INSERT ...")
cursor.execute("UPDATE ...")
```

### 错误处理
```python
# ✅ 正确：捕获异常
try:
    db.log_trade(...)
except Exception as e:
    logger.error(f"数据库操作失败: {e}")
    # 处理错误
```

### 数据验证
```python
# ✅ 正确：验证数据
def log_trade(self, symbol, side, amount, price):
    # 验证必需字段
    if not symbol or not side:
        raise ValueError("symbol和side是必需字段")

    # 验证数据类型
    if not isinstance(amount, (int, float)):
        raise TypeError("amount必须是数字")

    # 验证数据范围
    if amount <= 0:
        raise ValueError("amount必须大于0")

    # 执行插入
    ...
```

## 数据库迁移规范

### 添加新表
1. 在 `logger_utils.py` 的 `_init_db()` 方法中添加表定义
2. 使用 `CREATE TABLE IF NOT EXISTS` 确保幂等性
3. 添加必要的索引
4. 更新文档说明表的用途

### 添加新字段
```python
# ✅ 正确：使用ALTER TABLE
try:
    cursor.execute("ALTER TABLE trades ADD COLUMN new_field TEXT")
except sqlite3.OperationalError:
    # 字段已存在，忽略
    pass
```

### 修改字段
SQLite不支持直接修改字段，需要：
1. 创建新表
2. 复制数据
3. 删除旧表
4. 重命名新表

```python
# 示例
cursor.execute("CREATE TABLE trades_new (...)")
cursor.execute("INSERT INTO trades_new SELECT ... FROM trades")
cursor.execute("DROP TABLE trades")
cursor.execute("ALTER TABLE trades_new RENAME TO trades")
```

## 性能优化规范

### 查询优化
```python
# ✅ 正确：使用索引字段
SELECT * FROM trades WHERE created_at >= ? ORDER BY created_at DESC

# ❌ 错误：不使用索引
SELECT * FROM trades WHERE reason LIKE '%止损%'
```

### 批量操作
```python
# ✅ 正确：使用批量插入
cursor.executemany("INSERT INTO trades VALUES (?, ?, ?)", data_list)

# ❌ 错误：循环插入
for data in data_list:
    cursor.execute("INSERT INTO trades VALUES (?, ?, ?)", data)
```

### 数据清理
定期清理历史数据：
```python
# 删除30天前的持仓快照
DELETE FROM position_snapshots
WHERE created_at < datetime('now', '-30 days')
```

## Feature-Dev流程集成

### 在功能开发流程中的数据库规范

当功能开发涉及数据库修改时，必须在以下阶段遵循规范：

#### 阶段1：需求分析
- [ ] 确定是否需要新表或新字段
- [ ] 设计表结构和字段类型
- [ ] 规划索引策略

#### 阶段2：开发实施
- [ ] 备份数据库
- [ ] 在 `logger_utils.py` 中添加表定义
- [ ] 添加必要的索引
- [ ] 实现数据验证逻辑
- [ ] 添加错误处理

#### 阶段3：文档编写
- [ ] 更新数据库文档
- [ ] 记录表结构和字段说明
- [ ] 提供查询示例

#### 阶段4：测试
- [ ] 测试数据插入
- [ ] 测试数据查询
- [ ] 测试索引性能
- [ ] 测试错误处理

#### 阶段5：部署
- [ ] 验证数据库迁移成功
- [ ] 检查索引是否创建
- [ ] 验证数据完整性

## 数据库维护

### 日常维护
```bash
# 查看数据库大小
ls -lh trading_bot.db

# 查看表记录数
sqlite3 trading_bot.db "SELECT name, COUNT(*) FROM sqlite_master WHERE type='table'"

# 优化数据库
sqlite3 trading_bot.db "VACUUM"
```

### 定期任务
- **每周**: 检查数据库大小，清理旧数据
- **每月**: 优化数据库（VACUUM）
- **每季度**: 分析查询性能，优化索引

## 故障排查

### 常见问题

**问题1：数据库锁定**
```
sqlite3.OperationalError: database is locked
```
解决方案：
- 确保每次操作后关闭连接
- 使用事务减少锁定时间
- 考虑使用WAL模式

**问题2：数据库损坏**
```
sqlite3.DatabaseError: database disk image is malformed
```
解决方案：
- 从备份恢复
- 使用 `.recover` 命令恢复数据

**问题3：性能下降**
解决方案：
- 检查是否缺少索引
- 运行 VACUUM 优化
- 清理历史数据

## 最佳实践

### DO（推荐做法）
✅ 使用统一的数据库类进行操作
✅ 每次修改前备份数据库
✅ 为查询字段创建索引
✅ 使用事务处理批量操作
✅ 验证输入数据
✅ 捕获并记录异常
✅ 定期清理历史数据

### DON'T（禁止做法）
❌ 直接操作数据库文件
❌ 在循环中执行单条插入
❌ 忽略错误处理
❌ 不创建索引
❌ 不验证数据
❌ 不备份就修改结构

## 更新日志

### v1.0.0 (2025-12-24)
- 初始版本
- 定义数据库开发规范
- 添加索引优化
- 清理未使用的数据库文件

## 相关文档
- [logger_utils.py](../logger_utils.py) - 数据库操作核心类
- [config.py](../config.py) - 数据库配置
- [CHANGELOG.md](../CHANGELOG.md) - 更新日志
