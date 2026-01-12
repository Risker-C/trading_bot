"""
AI/Claude配置模块（Phase 1）
"""
import os

# ==================== Claude API配置 ====================

ENABLE_CLAUDE_ANALYSIS = True
CLAUDE_API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
CLAUDE_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# ==================== Claude分析参数 ====================

CLAUDE_MIN_SIGNAL_STRENGTH = 0.3
CLAUDE_TIMEOUT = 30
CLAUDE_FAILURE_MODE = "pass"

# ==================== Claude护栏配置 ====================

CLAUDE_CACHE_TTL = 300  # 5分钟
CLAUDE_MAX_DAILY_CALLS = 500
CLAUDE_MAX_DAILY_COST = 10.0

# ==================== Claude定时分析 ====================

ENABLE_CLAUDE_PERIODIC_ANALYSIS = False
CLAUDE_PERIODIC_INTERVAL = 30  # 30分钟
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'standard'
CLAUDE_ANALYZE_ON_STARTUP = False
CLAUDE_PUSH_TO_FEISHU = True

# ==================== Claude每日报告 ====================

ENABLE_CLAUDE_DAILY_REPORT = True
CLAUDE_DAILY_REPORT_HOUR = 8
CLAUDE_DAILY_REPORT_TIMEZONE = 'Asia/Shanghai'
CLAUDE_DAILY_INCLUDE_TRADE_REVIEW = True

# ==================== Phase 0: AI异步化 ====================

ASYNC_AI_ENABLED = False  # 是否启用AI异步调用
