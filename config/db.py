"""
数据库与日志配置模块（Phase 1）
"""

# ==================== 数据库配置 ====================

# 数据库路径（从paths.py导入，这里保留兼容性）
# DB_PATH 已在 paths.py 中定义

# 数据存储选项
SAVE_EQUITY_CURVE = True

# Phase 0: 数据库批量写入开关
DB_BATCH_WRITES_ENABLED = True  # 启用批量写入以提升性能

# Phase 3: 批量写入参数（建议 10-50 条）
DB_BATCH_SIZE = 20
# 批量写入的最大等待时间（秒）
DB_BATCH_FLUSH_INTERVAL = 5

# ==================== 日志配置 ====================

LOG_LEVEL = "DEBUG"

# 日志分流配置
ENABLE_LOG_SPLITTING = True
