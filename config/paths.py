"""
路径配置模块（Phase 1）
"""

# ==================== 数据存储路径 ====================

DB_PATH = "trading_bot.db"

# ==================== 日志路径 ====================

LOG_DIR = "logs"
LOG_FILE = "trading_bot.log"  # 主日志文件（已废弃，保留兼容性）

# 分流日志文件
LOG_FILE_INFO = "info.log"
LOG_FILE_ERROR = "error.log"
LOG_FILE_DEBUG = "debug.log"
LOG_FILE_WARNING = "warning.log"

# ==================== 模型路径 ====================

ML_MODEL_PATH = "models/signal_quality_v1.pkl"
