"""
策略配置模块（Phase 1）
"""
from typing import List

# ==================== 启用策略列表 ====================

ENABLE_STRATEGIES: List[str] = [
    "bollinger_trend",
    "macd_cross",
    "ema_cross",
    "composite_score",
    "multi_timeframe",
    "adx_trend",
]

# ==================== 共识信号配置 ====================

USE_CONSENSUS_SIGNAL = True
MIN_STRATEGY_AGREEMENT = 0.35
MIN_SIGNAL_STRENGTH = 0.40
MIN_SIGNAL_CONFIDENCE = 0.30

# ==================== 动态策略选择 ====================

USE_DYNAMIC_STRATEGY = True

# ==================== 技术指标参数 ====================

# RSI
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# 注：更多技术指标参数保留在原config.py中，待后续迁移
