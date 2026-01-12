"""
运行时配置模块（Phase 1）
"""

# ==================== 运行时间隔 ====================

CHECK_INTERVAL = 5             # 检查间隔（秒）
HEARTBEAT_INTERVAL = 300       # 心跳间隔（秒）
HEALTH_CHECK_INTERVAL = 600    # 健康检查间隔（秒）

# ==================== 错误处理 ====================

MAX_API_ERRORS = 5             # 最大连续错误次数
API_ERROR_COOLDOWN = 30        # 错误后冷却时间（秒）
AUTO_RECONNECT = True          # 自动重连

# ==================== API性能 ====================

MAX_API_LATENCY_MS = 500       # 最大API延迟（毫秒）
