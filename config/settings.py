"""
配置文件 - 增强版
整合 Qbot 功能后的完整配置
"""
import os
from typing import List, Dict
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ==================== 多交易所配置 ====================

# 当前使用的交易所
ACTIVE_EXCHANGE = os.getenv("ACTIVE_EXCHANGE", "bitget")

# 多交易所配置
EXCHANGES_CONFIG = {
    "bitget": {
        "api_key": os.getenv("BITGET_API_KEY", ""),
        "api_secret": os.getenv("BITGET_API_SECRET") or os.getenv("BITGET_SECRET", ""),
        "api_password": os.getenv("BITGET_API_PASSWORD") or os.getenv("BITGET_PASSWORD", ""),
        "symbol": "BTCUSDT",
        "product_type": "USDT-FUTURES",
        "leverage": 50,
        "margin_mode": "crossed",
        "maker_fee": 0.0002,
        "taker_fee": 0.0006,
    },
    "binance": {
        "api_key": os.getenv("BINANCE_API_KEY", ""),
        "api_secret": os.getenv("BINANCE_API_SECRET", ""),
        "api_password": None,
        "symbol": "BTCUSDT",
        "leverage": 50,
        "margin_mode": "crossed",
        "maker_fee": 0.0002,
        "taker_fee": 0.0004,
    },
    "okx": {
        "api_key": os.getenv("OKX_API_KEY", ""),
        "api_secret": os.getenv("OKX_API_SECRET", ""),
        "api_password": os.getenv("OKX_API_PASSWORD", ""),
        "symbol": "BTCUSDT",
        "leverage": 50,
        "margin_mode": "crossed",
        "maker_fee": 0.0002,
        "taker_fee": 0.0005,
    }
}

# 向后兼容：保持EXCHANGE_CONFIG指向当前激活的交易所
EXCHANGE_CONFIG = EXCHANGES_CONFIG.get(ACTIVE_EXCHANGE, EXCHANGES_CONFIG["bitget"])

SYMBOL = "BTCUSDT"
PRODUCT_TYPE = "USDT-FUTURES"  # USDT 合约
TIMEFRAME = "15m"              # 主时间周期
KLINE_LIMIT = 200              # K线数量

# ==================== 多时间周期配置（新增）====================

MULTI_TIMEFRAME_ENABLED = True
TIMEFRAMES = ["15m", "1h"]  # 从4个周期优化为2个周期，减少数据获取量
TIMEFRAME_WEIGHTS = {
    "15m": 0.45,  # 调整权重
    "1h": 0.55,
}


# 异步数据获取配置
USE_ASYNC_DATA_FETCH = True  # 启用异步并发获取多时间周期数据
USE_ASYNC_MAIN_LOOP = False  # 启用异步主循环（实验性功能）
# ==================== 杠杆和保证金 ====================

LEVERAGE = 50
MARGIN_MODE = "crossed"  # isolated / crossed

# ==================== 仓位管理 ====================

POSITION_SIZE_PERCENT = 0.05   # Phase 1 优化: 提升至5%以增加收益基数（目标日收益2-3%）
MIN_ORDER_USDT = 10            # 最小订单金额
MAX_ORDER_USDT = 1000          # 最大订单金额
MIN_AMOUNT_PRECISION = 0.0001  # 最小数量精度（BTC）

# 分批建仓配置（新增）
USE_PARTIAL_POSITION = True    # 是否分批建仓
POSITION_PARTS = 3             # 分几批建仓
POSITION_ENTRY_TYPE = "pyramid"  # pyramid / equal / reverse_pyramid

# ==================== Kelly 公式配置（新增）====================

USE_KELLY_CRITERION = True     # 是否使用 Kelly 公式
KELLY_FRACTION = 0.6           # Phase 1 优化: 提升至0.6（更激进的Kelly系数）
MIN_WIN_RATE_FOR_KELLY = 0.35  # Phase 1 优化: 降至0.35（更早启用Kelly）

# ==================== 波动率配置（新增）====================

REDUCE_SIZE_ON_HIGH_VOL = True        # 高波动时减仓
HIGH_VOLATILITY_THRESHOLD = 0.08      # Phase 1 优化: 提升至8%（提高高波动阈值）
LOW_VOLATILITY_THRESHOLD = 0.01       # 低波动阈值（1%）
VOLATILITY_SIZE_FACTOR = 0.8          # Phase 1 优化: 提升至0.8（减少高波动减仓幅度）
VOLATILITY_LOOKBACK = 20              # 波动率计算周期

# ==================== 止损止盈配置 ====================

STOP_LOSS_PERCENT = 0.045      # 止损比例 4.5% (保持不变)
TAKE_PROFIT_PERCENT = 0.05     # Phase 1 优化: 提升至5%（扩大止盈空间，单笔收益+67%）
TRAILING_STOP_PERCENT = 0.04   # Phase 1 优化: 提升至4%（给盈利单更多空间）

# ATR 动态止损（新增）
USE_ATR_STOP_LOSS = True       # 是否使用 ATR 止损
ATR_STOP_MULTIPLIER = 4.0      # ATR 倍数 (优化：从3.5提高到4.0，减少被市场波动打止损)

# 分批止盈（新增）
USE_PARTIAL_TAKE_PROFIT = True # 是否分批止盈

# ==================== 策略级差异化止损配置（新增）====================

# 是否启用策略级差异化止损
USE_STRATEGY_SPECIFIC_STOPS = True

# 策略级止损配置（基于策略表现优化）
# 格式：策略名 -> {stop_loss_pct, take_profit_pct, trailing_stop_pct, atr_multiplier}
STRATEGY_STOP_CONFIGS = {
    # 表现优秀的策略 - 给予更多空间
    "multi_timeframe": {
        "stop_loss_pct": 0.05,      # 5% 止损（盈亏比1.76，需要更多空间）
        "take_profit_pct": 0.06,    # Phase 1 优化: 提升至6%（最大化优秀策略收益）
        "trailing_stop_pct": 0.04,  # Phase 1 优化: 提升至4%
        "atr_multiplier": 4.5,      # ATR倍数4.5
    },
    # 表现中等的策略 - 标准配置
    "adx_trend": {
        "stop_loss_pct": 0.045,     # 4.5% 止损（盈亏比0.97，标准配置）
        "take_profit_pct": 0.05,    # Phase 1 优化: 提升至5%（与全局一致）
        "trailing_stop_pct": 0.04,  # Phase 1 优化: 提升至4%
        "atr_multiplier": 4.0,      # ATR倍数4.0
    },
    # 其他策略使用默认配置
}

# ==================== 动态止盈配置 ====================

# 是否启用动态止盈（基于浮动盈利门槛和回撤均值）
ENABLE_TRAILING_TAKE_PROFIT = True

# 最小盈利门槛（USDT）- 必须超过此值才算真正盈利
# 优化说明：从0.012提高到0.08，避免过早触发动态止盈，让盈利交易有更多空间
# 保守方案：改为基于手续费的动态计算，使用倍数参数
MIN_PROFIT_THRESHOLD_USDT = 0.08  # 保留作为后备值，实际使用动态计算

# 动态止盈门槛倍数（基于总手续费）
# 例如：1.5表示盈利必须超过总手续费的1.5倍才启用动态止盈
# 对于10 USDT仓位，总手续费约0.012 USDT，门槛为0.018 USDT（约0.18%盈利）
MIN_PROFIT_THRESHOLD_MULTIPLIER = 1.2  # Phase 1 优化: 降至1.2倍（更早启用动态止盈）

# 价格均值窗口大小（N次价格）
# 建议：5-10次，平衡灵敏度和稳定性
TRAILING_TP_PRICE_WINDOW = 5

# 跌破均值的百分比阈值（例如：0.0008 表示跌破0.08%）
# 修复说明：从0.4%降低到0.08%，提高动态止盈灵敏度，避免盈利变亏损
TRAILING_TP_FALLBACK_PERCENT = 0.001  # Phase 1 优化: 提升至0.1%（放宽回撤阈值）

# ==================== Maker订单配置（新增）====================

# 是否启用Maker订单（限价单）
USE_MAKER_ORDER = True  # True: 使用限价单（手续费0.02%），False: 使用市价单（手续费0.06%）

# Maker订单超时时间（秒）
# 如果限价单在此时间内未成交，将自动取消并转为市价单
MAKER_ORDER_TIMEOUT = 10  # 10秒超时

# Maker订单价格偏移量（百分比）
# 做多时：挂单价格 = 当前价格 * (1 - offset)，即略低于市价
# 做空时：挂单价格 = 当前价格 * (1 + offset)，即略高于市价
MAKER_PRICE_OFFSET = 0.0001  # 0.01%的价格偏移，确保成为Maker

# Maker订单检查间隔（秒）
MAKER_ORDER_CHECK_INTERVAL = 0.5  # 每0.5秒检查一次订单状态

# 是否在Maker订单失败时自动降级为市价单
MAKER_AUTO_FALLBACK_TO_MARKET = True  # 建议开启，避免错过交易机会

# 手续费率配置
TRADING_FEE_RATE_MAKER = 0.0002  # Bitget Maker费率 0.02%
TRADING_FEE_RATE_TAKER = 0.0006  # Bitget Taker费率 0.06%

# 当前使用的手续费率（根据USE_MAKER_ORDER自动选择）
TRADING_FEE_RATE = TRADING_FEE_RATE_MAKER if USE_MAKER_ORDER else TRADING_FEE_RATE_TAKER

# ==================== 动态Maker订单配置（新增）====================

# 是否启用动态Maker订单（根据信号强度和波动率自适应）
ENABLE_DYNAMIC_MAKER = True  # True: 启用动态调整，False: 使用固定参数

# 信号强度阈值
MAKER_MIN_SIGNAL_STRENGTH = 0.6  # 低于此值直接使用市价单（避免弱信号浪费时间）
MAKER_OPTIMAL_SIGNAL_STRENGTH = 0.8  # 高于此值使用最优参数（强信号值得等待）

# 波动率自适应参数
MAKER_HIGH_VOL_TIMEOUT = 5  # 高波动超时（秒）- 快速决策
MAKER_LOW_VOL_TIMEOUT = 15  # 低波动超时（秒）- 耐心等待
MAKER_HIGH_VOL_OFFSET = 0.0002  # 高波动偏移（0.02%）- 增大偏移提高成交率
MAKER_LOW_VOL_OFFSET = 0.00005  # 低波动偏移（0.005%）- 减小偏移降低滑点

# 极端波动禁用Maker订单
MAKER_DISABLE_ON_EXTREME_VOL = True  # 极端波动时强制使用市价单
MAKER_EXTREME_VOL_THRESHOLD = 0.08  # 极端波动阈值（8%）

# ==================== 动态价格更新配置 ====================

# 是否启用动态价格更新频率（开仓后提高更新频率）
ENABLE_DYNAMIC_CHECK_INTERVAL = True

# 默认检查间隔（秒）- 无持仓时
DEFAULT_CHECK_INTERVAL = 5

# 持仓时检查间隔（秒）- 有持仓时提高频率
POSITION_CHECK_INTERVAL = 2

# ==================== 错误退避控制器配置 (Error Backoff Controller) ====================

# 是否启用错误退避控制器
ENABLE_ERROR_BACKOFF = True

# 最小退避时间（秒）
ERROR_BACKOFF_MIN_SECONDS = 120  # 2分钟

# 最大退避时间（秒）
ERROR_BACKOFF_MAX_SECONDS = 3600  # 1小时

# 退避倍数（指数退避）
ERROR_BACKOFF_MULTIPLIER = 2.0

# 错误重置时间（秒）- 超过此时间后重置错误计数
ERROR_RESET_SECONDS = 1800  # 30分钟

# ==================== 价格稳定性检测配置 (Price Stability Detection) ====================

# 是否启用价格稳定性检测
PRICE_STABILITY_ENABLED = True

# 价格稳定性观察窗口（秒）
PRICE_STABILITY_WINDOW_SECONDS = 5.0

# 价格稳定性波动阈值（百分比）
PRICE_STABILITY_THRESHOLD_PCT = 0.5  # 0.5%

# 价格采样间隔（秒）
PRICE_STABILITY_SAMPLE_INTERVAL = 1.0

# ==================== 订单健康检查配置 (Order Health Checker) ====================

# 是否启用订单健康检查
ORDER_HEALTH_CHECK_ENABLED = True

# 订单健康检查间隔（秒）
ORDER_HEALTH_CHECK_INTERVAL = 300  # 5分钟

# 订单最大存活时间（秒）
ORDER_MAX_AGE_SECONDS = 3600  # 1小时

# 订单过期阈值（秒）
ORDER_STALE_THRESHOLD_SECONDS = 600  # 10分钟

# ==================== 流动性验证配置 (Liquidity Validation) ====================

# 是否启用流动性验证
LIQUIDITY_VALIDATION_ENABLED = True

# 最小订单簿深度要求（相对于订单数量的倍数）
MIN_ORDERBOOK_DEPTH_MULTIPLIER = 2.0  # 对手盘深度至少是订单数量的2倍

# 最小绝对深度要求（USDT）
MIN_ORDERBOOK_DEPTH_USDT = 1000  # 对手盘至少1000 USDT

# 订单簿数据新鲜度要求（秒）
ORDERBOOK_DATA_FRESHNESS_SECONDS = 5.0  # 只使用5秒内的数据

# 流动性不足时的处理策略
LIQUIDITY_INSUFFICIENT_ACTION = "reject"  # reject=拒绝订单, reduce=减少订单量, ignore=忽略

# ==================== 策略配置 ====================
# ==================== Band-Limited Hedging 策略配置 ====================
# Band-Limited 策略已启用，其他策略已禁用

ENABLE_STRATEGIES: List[str] = [
    "band_limited_hedging",  # Band-Limited Dynamic Hedging 策略（双向持仓）
]

# Band-Limited 策略参数（可选，不配置则使用默认值）
BAND_LIMITED_PARAMS = {
    "MES": 0.009,              # Minimum Effective Scale (默认: 9 * fee_rate = 0.009)
    "alpha": 0.5,              # 利润迁移比例 (默认: 0.5)
    "base_position_ratio": 0.95,  # 基础仓位维持比例 (默认: 0.95，即使用95%资金)
    "min_rebalance_profit": 0.0,  # 固定利润阈值 (默认: 0.0)
    "min_rebalance_profit_ratio": 1.0,  # 动态利润阈值倍数 (默认: 1.0)
    "fee_rate": 0.001,         # 交易手续费率 (默认: 0.001)
    # 退出参数
    "eta": 0.2,                # 退出减仓比例 (默认: 0.2)
    "exit_mes_ratio": 0.7,     # 退出MES比例 (默认: 0.7)
    "exit_sigma_k": 0.01,      # 低波动退出系数 (默认: 0.01)
    "exit_sigma_consecutive": 10,  # 连续低波动次数 (默认: 10)
}

# 注意：Band-Limited 策略需要单策略模式运行，不能与其他策略混用

# ==================== 其他策略（已禁用）====================
# 以下策略在 Band-Limited 模式下不会被执行
# ENABLE_STRATEGIES: List[str] = [
#     "bollinger_trend",
#     "macd_cross",
#     "ema_cross",
#     "composite_score",
#     "multi_timeframe",
#     "adx_trend",
# ]

# 共识信号配置
USE_CONSENSUS_SIGNAL = True        # 是否使用共识信号
MIN_STRATEGY_AGREEMENT = 0.35      # 最小策略一致性（降至0.35提升交易频率）
MIN_SIGNAL_STRENGTH = 0.30         # 最小信号强度（降至0.30增加交易机会）
MIN_SIGNAL_CONFIDENCE = 0.25       # 最小信号置信度（降至0.25放宽过滤）

# 动态策略选择配置
USE_DYNAMIC_STRATEGY = False       # 禁用动态策略（震荡市策略不生成信号）
# 当启用时,系统会根据市场状态(震荡/过渡/趋势)自动选择合适的策略
# 当禁用时,使用上面 ENABLE_STRATEGIES 中的固定策略列表

# ==================== 技术指标参数 ====================

# RSI
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# 布林带
BB_PERIOD = 20
BB_STD = 2.0
BB_STD_DEV = BB_STD  # 别名
BB_BREAKTHROUGH_COUNT = 3  # 突破确认周期数
REVERSE_CANDLE_COUNT = 3  # 反转K线确认数量

# EMA
EMA_SHORT = 9
EMA_LONG = 21
EMA_PERIODS = [9, 21, 55, 100, 200]

# KDJ
KDJ_K_PERIOD = 9
KDJ_D_PERIOD = 3
KDJ_PERIOD = KDJ_K_PERIOD  # 别名
KDJ_SIGNAL_PERIOD = KDJ_D_PERIOD  # 别名
KDJ_OVERSOLD = 20
KDJ_OVERBOUGHT = 80

# ADX（新增）
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25

# 市场状态判断阈值（优化版）
STRONG_TREND_ADX = 35.0           # 强趋势ADX阈值（超过此值时放宽布林带要求）
STRONG_TREND_BB = 2.0             # 强趋势时的布林带宽度阈值（%）
TREND_EXIT_ADX = 27.0             # 趋势退出ADX阈值（滞回机制）
TREND_EXIT_BB = 2.5               # 趋势退出布林带宽度阈值（%）
TRANSITIONING_CONFIDENCE_THRESHOLD = 0.25  # 过渡市置信度阈值（降低以允许更多交易）

# ATR
ATR_PERIOD = 14

# ==================== 网格策略配置（新增）====================

GRID_UPPER_PRICE = 0           # 0 表示自动计算
GRID_LOWER_PRICE = 0
GRID_NUM = 10                  # 网格数量
GRID_TYPE = "arithmetic"       # arithmetic / geometric

# ==================== 运行时配置 ====================

CHECK_INTERVAL = 5             # 检查间隔（秒）
HEARTBEAT_INTERVAL = 300       # 心跳间隔（秒）
HEALTH_CHECK_INTERVAL = 600    # 健康检查间隔（秒）

# 错误处理
MAX_API_ERRORS = 5             # 最大连续错误次数
API_ERROR_COOLDOWN = 30        # 错误后冷却时间（秒）
AUTO_RECONNECT = True          # 自动重连

# ==================== 数据存储 ====================

DB_PATH = os.getenv("DATABASE_PATH", "trading_bot.db")
LOG_DIR = "logs"
LOG_FILE = "trading_bot.log"       # 主日志文件（已废弃，保留兼容性）
LOG_LEVEL = "INFO"  # 从DEBUG优化为INFO，减少日志开销
SAVE_EQUITY_CURVE = True

# 数据库批量写入配置（性能优化）
DB_BATCH_SIZE = 50                 # 从20优化为50，减少写入频率
DB_BATCH_FLUSH_INTERVAL = 10.0     # 从5秒优化为10秒，减少刷新频率

# ==================== 错误处理配置 ====================

# 主循环错误处理
MAX_CONSECUTIVE_ERRORS = 5         # 最大连续错误次数
ERROR_BACKOFF_SECONDS = 10         # 错误退避基础时间（秒）

# ==================== 日志分流配置 ====================

# 是否启用日志分流（多文件存储）
ENABLE_LOG_SPLITTING = True

# 各级别日志文件名
LOG_FILE_INFO = "info.log"         # INFO 级别日志
LOG_FILE_ERROR = "error.log"       # ERROR 级别日志
LOG_FILE_DEBUG = "debug.log"       # DEBUG 级别日志
LOG_FILE_WARNING = "warning.log"   # WARNING 级别日志

# 日志轮转配置
LOG_ROTATION_WHEN = "midnight"     # 按天轮转：midnight
LOG_ROTATION_INTERVAL = 1          # 轮转间隔：1天
LOG_ROTATION_BACKUP_COUNT = 30     # 保留30天的日志备份

# 控制台输出配置
CONSOLE_LOG_LEVEL = "INFO"         # 控制台显示级别（聚合观察视图）- 改为 DEBUG 可查看所有日志
CONSOLE_SHOW_ALL_LEVELS = True     # 控制台是否显示所有级别（观察层）

# ==================== Telegram 通知（新增）====================

ENABLE_TELEGRAM = False
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ==================== 飞书通知 ====================

ENABLE_FEISHU = True
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")

# ==================== 邮件通知 ====================

ENABLE_EMAIL = True
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")

# ==================== 定期市场报告配置（新增）====================

# 是否启用定期市场报告
ENABLE_PERIODIC_REPORT = True

# 报告发送间隔（分钟）
PERIODIC_REPORT_INTERVAL = 120  # 默认2小时

# 报告详细程度: 'simple', 'standard', 'detailed'
PERIODIC_REPORT_DETAIL_LEVEL = 'standard'

# 是否在启动时立即发送一次报告
SEND_REPORT_ON_STARTUP = True

# 报告包含的模块（可选配置）
PERIODIC_REPORT_MODULES = {
    'system_info': True,      # 系统信息
    'market_info': True,      # 市场信息
    'market_state': True,     # 市场状态
    'strategy_info': True,    # 策略信息
    'position_info': True,    # 持仓信息
    'account_info': True,     # 账户信息
    'trade_stats': True,      # 交易统计
}

# ==================== 状态监控配置（新增）====================

# 是否启用状态监控推送
ENABLE_STATUS_MONITOR = True

# 状态推送间隔（分钟）
STATUS_MONITOR_INTERVAL = 15  # 优化：从5分钟改为15分钟，减少推送频率

# 是否启用AI分析（预留功能）
STATUS_MONITOR_ENABLE_AI = False

# 飞书推送失败时是否发送邮件预警
STATUS_MONITOR_EMAIL_ON_FAILURE = True

# 状态监控包含的模块
STATUS_MONITOR_MODULES = {
    'market_change': True,    # 最近N分钟行情变化
    'trade_activity': True,   # 开单情况
    'trend_analysis': True,   # 趋势分析
    'service_status': True,   # 服务状态
    'account_info': True,     # 账户信息
}

# ==================== 飞书推送过滤配置（新增）====================

# 是否启用飞书推送智能过滤
ENABLE_FEISHU_PUSH_FILTER = True

# 行情变化阈值（只推送变化超过此值的行情）
FEISHU_PRICE_CHANGE_THRESHOLD = 0.005  # 0.5%，低于此值不推送行情变化

# 无持仓时是否简化推送内容
FEISHU_SIMPLIFY_NO_POSITION = True  # 无持仓时只推送关键信息

# 无持仓且无显著行情变化时是否跳过推送
FEISHU_SKIP_IDLE_PUSH = True  # 无持仓且行情变化小时跳过推送

# 推送频率限制（同类型推送的最小间隔，分钟）
FEISHU_MIN_PUSH_INTERVAL = {
    'status_monitor': 15,     # 状态监控最小间隔15分钟
    'market_report': 120,     # 市场报告最小间隔120分钟
    'trade': 0,               # 交易通知不限制（重要）
    'signal': 5,              # 信号通知最小间隔5分钟
    'risk_event': 0,          # 风控事件不限制（重要）
}

# 是否过滤重复内容推送
FEISHU_FILTER_DUPLICATE_CONTENT = True  # 内容与上次相同时跳过推送

# 重复内容判断的相似度阈值（0-1）
FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = 0.9  # 90%相似度视为重复

# 是否在非交易时段降低推送频率
FEISHU_REDUCE_OFF_HOURS = True  # 非交易活跃时段降低推送

# 非交易活跃时段定义（小时，24小时制）
FEISHU_OFF_HOURS = list(range(0, 6)) + list(range(22, 24))  # 0-6点和22-24点

# 非交易时段推送间隔倍数
FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER = 2.0  # 非活跃时段间隔翻倍

# ==================== Claude AI 分析配置（新增）====================

# 是否启用 Claude AI 分析
ENABLE_CLAUDE_ANALYSIS = True  # 启用实时信号分析

# Claude API配置（从环境变量读取）
CLAUDE_API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")  # 使用ANTHROPIC_AUTH_TOKEN
CLAUDE_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")  # 自定义API端点

# Claude 模型选择
# 可选: claude-opus-4-5-20251101 (最强), claude-sonnet-4-5-20250929 (平衡), claude-haiku-4-20250514 (快速)
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# Claude API超时配置（秒）
CLAUDE_TIMEOUT = 30  # API调用超时时间，避免阻塞

# Claude 分析的最小信号强度阈值（低于此值不调用 Claude）
CLAUDE_MIN_SIGNAL_STRENGTH = 0.3

# Claude 分析失败时的默认行为
# "pass": 分析失败时默认通过信号
# "reject": 分析失败时默认拒绝信号
CLAUDE_FAILURE_MODE = "pass"

# ==================== 影子模式配置（新增）====================

# 是否启用影子模式（记录所有决策但不影响执行）
ENABLE_SHADOW_MODE = False  # 默认关闭，建议先观察1-2天再启用

# ==================== Claude护栏配置（新增）====================

# Claude缓存时间（秒）
CLAUDE_CACHE_TTL = 300  # 5分钟

# Claude日调用上限
CLAUDE_MAX_DAILY_CALLS = 500

# Claude日成本上限（美元）
CLAUDE_MAX_DAILY_COST = 10.0

# ==================== Claude定时分析配置（新增）====================

# 是否启用Claude定时分析
ENABLE_CLAUDE_PERIODIC_ANALYSIS = False  # 启用定时市场分析（每30分钟）

# 定时分析间隔（分钟）- 用于场景2：30分钟定时分析
CLAUDE_PERIODIC_INTERVAL = 30  # 默认30分钟

# 分析详细程度: 'simple', 'standard', 'detailed'
CLAUDE_ANALYSIS_DETAIL_LEVEL = 'standard'

# 是否在启动时立即分析一次
CLAUDE_ANALYZE_ON_STARTUP = False  # 改为False，避免启动时不必要的调用

# 是否通过飞书推送分析结果
CLAUDE_PUSH_TO_FEISHU = True

# 分析包含的模块
CLAUDE_ANALYSIS_MODULES = {
    'market_trend': True,      # 市场趋势分析
    'risk_assessment': True,   # 风险评估
    'entry_opportunities': True,  # 入场机会
    'position_advice': True,   # 持仓建议
    'market_sentiment': True,  # 市场情绪
}

# ==================== Claude每日报告配置（新增）====================

# 是否启用Claude每日报告 - 场景3：每天早上8点的报告
ENABLE_CLAUDE_DAILY_REPORT = True  # 启用每日报告（早上8点）

# 每日报告时间（小时，24小时制）
CLAUDE_DAILY_REPORT_HOUR = 8  # 早上8点

# 每日报告时区
CLAUDE_DAILY_REPORT_TIMEZONE = 'Asia/Shanghai'  # 东八区

# 是否包含交易历史回顾（需要网络检索）
CLAUDE_DAILY_INCLUDE_TRADE_REVIEW = True

# 是否包含实时网络信息分析
CLAUDE_DAILY_INCLUDE_WEB_SEARCH = True

# 回顾天数（昨日交易）
CLAUDE_DAILY_REVIEW_DAYS = 1

# ==================== Policy Layer 配置（新增）====================

# 是否启用 Policy Layer（策略治理层）
ENABLE_POLICY_LAYER = False  # 临时禁用，先稳定基础配置后再启用动态调整

# Policy Layer 更新间隔（分钟）
# Claude 会定期分析交易上下文并更新策略参数
POLICY_UPDATE_INTERVAL = 30  # 默认30分钟

# Policy Layer 模式
# "shadow": 影子模式（只记录不生效，用于观察）
# "active": 主动模式（真实影响交易参数）
POLICY_LAYER_MODE = "active"  # 已切换到主动模式

# 是否在启动时立即执行一次 Policy 分析
POLICY_ANALYZE_ON_STARTUP = True

# Policy 决策的默认 TTL（分钟）
POLICY_DEFAULT_TTL = 30

# Policy Layer 参数边界（安全约束）
POLICY_PARAM_BOUNDS = {
    'stop_loss_pct': (0.005, 0.05),      # 0.5% - 5%
    'take_profit_pct': (0.01, 0.10),     # 1% - 10%
    'trailing_stop_pct': (0.005, 0.03),  # 0.5% - 3%
    'position_multiplier': (0.3, 2.0),   # 0.3x - 2.0x
}

# 风控模式自动切换规则
POLICY_AUTO_RISK_MODE = True  # 是否允许自动切换风控模式

# 连续亏损触发防守模式的阈值
POLICY_DEFENSIVE_LOSS_THRESHOLD = 3

# 连续盈利触发激进模式的阈值
POLICY_AGGRESSIVE_WIN_THRESHOLD = 5

# ==================== 执行层风控配置（新增）====================

# 是否启用执行层风控
ENABLE_EXECUTION_FILTER = False  # Phase 1 优化: 临时禁用执行层风控（提升交易通过率20%）

# 点差阈值（超过此值拒绝交易）
MAX_SPREAD_PCT = 0.001  # 0.1%

# 滑点阈值
MAX_SLIPPAGE_PCT = 0.002  # 0.2%

# 最小成交量比率（低于此值拒绝交易）
MIN_VOLUME_RATIO = 0.5  # 50%

# ATR突增阈值（超过此倍数延迟进场）
ATR_SPIKE_THRESHOLD = 1.5  # 1.5倍

# ==================== 方向过滤器配置（新增）====================

# 是否启用方向过滤器（解决做多胜率低的问题）
ENABLE_DIRECTION_FILTER = False  # Phase 1: 临时禁用以恢复交易活动

# 做多信号要求（适度严格的标准）
LONG_MIN_STRENGTH = 0.65       # 做多需要65%信号强度（优化：从80%降低，过高要求导致无法开仓）
LONG_MIN_AGREEMENT = 0.65      # 做多需要65%策略一致性（优化：从80%降低，恢复交易频率）

# 做空信号要求（正常标准）
SHORT_MIN_STRENGTH = 0.5       # 做空保持50%信号强度
SHORT_MIN_AGREEMENT = 0.6      # 做空保持60%策略一致性

# 是否启用自适应阈值调整（根据历史胜率动态调整）
ENABLE_ADAPTIVE_THRESHOLDS = False  # Phase 1: 禁用以打破恶性循环

# 自适应调整的触发条件
ADAPTIVE_LOW_WIN_RATE = 0.3    # 做多胜率低于30%时提高要求
ADAPTIVE_HIGH_WIN_RATE = 0.4   # 做空胜率高于40%时放宽要求

# ==================== 仓位管理配置（增强）====================

# 目标波动率（用于波动率调整仓位）
TARGET_VOLATILITY = 0.02  # 2%

# 仓位调整倍数范围
MAX_POSITION_MULTIPLIER = 2.0  # 最大2倍
MIN_POSITION_MULTIPLIER = 0.5  # 最小0.5倍

# 单日最大亏损比例（触发熔断）
MAX_DAILY_LOSS_PCT = 0.05  # 5%

# ==================== 回测配置（新增）====================

BACKTEST_START_DATE = "2024-01-01"
BACKTEST_END_DATE = "2024-12-01"
BACKTEST_INITIAL_BALANCE = 10000
BACKTEST_COMMISSION = 0.0006   # 手续费率
BACKTEST_SLIPPAGE = 0.0001     # 滑点

# ==================== ML信号过滤器配置（新增）====================

# 是否启用ML信号过滤器
ENABLE_ML_FILTER = True  # 已启用，使用影子模式测试

# 是否使用轻量级优化版ML预测器
ML_USE_LITE_VERSION = True  # True: 使用优化版（推荐，内存占用低60-70%），False: 使用原版

# ML运行模式
ML_MODE = "shadow"  # shadow: 影子模式（只记录不影响交易）, filter: 过滤模式（实际过滤信号）, off: 关闭

# ML模型路径
ML_MODEL_PATH = "models/signal_quality_v1.pkl"

# ML信号质量阈值（0-1，只执行质量分数>=此值的信号）
# 优化说明：从0.6降低到0.35，因为当前模型预测分数在24-29%范围内
# 降低阈值可以让高质量信号通过，避免过度过滤
ML_QUALITY_THRESHOLD = 0.35  # 35%质量分数（优化后）

# ML最小信号数量（如果过滤后信号数量<此值，则不过滤）
ML_MIN_SIGNALS = 1

# 是否记录ML预测结果到数据库
ML_LOG_PREDICTIONS = True

# 是否在日志中显示ML预测详情
ML_VERBOSE_LOGGING = False  # 从True优化为False，减少日志输出

# ML特征工程配置
ML_FEATURE_LOOKBACK = 20  # 特征计算回溯周期（K线数量）

# ML模型更新配置
ML_AUTO_RETRAIN = False  # 是否自动重新训练模型
ML_RETRAIN_INTERVAL_DAYS = 30  # 重新训练间隔（天）
ML_MIN_TRAINING_SAMPLES = 100  # 最小训练样本数


# ==================== 跨交易所套利配置 ====================

# 是否启用套利引擎
ENABLE_ARBITRAGE = False  # 关闭套利引擎以降低CPU和内存占用

# 套利模式
ARBITRAGE_MODE = "conservative"  # conservative: 保守模式, balanced: 平衡模式, aggressive: 激进模式

# 交易对配置
ARBITRAGE_SYMBOL = "BTCUSDT"  # 套利交易对
ARBITRAGE_EXCHANGES = ["bitget", "binance", "okx"]  # 参与套利的交易所

# 价差监控配置
SPREAD_MONITOR_INTERVAL = 3  # 从1秒优化为3秒，减少监控频率
SPREAD_HISTORY_SIZE = 50  # 从100优化为50，减少内存占用
SPREAD_ALERT_THRESHOLD = 1.0  # 价差告警阈值（%）

# 机会检测配置
MIN_SPREAD_THRESHOLD = 0.25  # Phase 1 优化: 降至0.25%（增加套利机会）
MIN_NET_PROFIT_THRESHOLD = 1.0  # 最小净利润阈值（USDT）
MIN_PROFIT_RATIO = 0.5  # 最小利润比例（净利润/毛利润）
OPPORTUNITY_SCAN_INTERVAL = 2  # 机会扫描间隔（秒）

# 仓位管理配置
ARBITRAGE_POSITION_SIZE = 150  # Phase 1 优化: 提升至150 USDT（增加套利收益）
MAX_POSITION_PER_EXCHANGE = 500  # 单交易所最大持仓（USDT）
MAX_TOTAL_ARBITRAGE_EXPOSURE = 1000  # 总套利敞口限制（USDT）
MAX_POSITION_COUNT_PER_EXCHANGE = 3  # 单交易所最大持仓数量

# 频率限制配置
MAX_ARBITRAGE_PER_HOUR = 15  # Phase 1 优化: 提升至15次（增加套利频率）
MAX_ARBITRAGE_PER_DAY = 50  # 每日最大套利次数
MIN_INTERVAL_BETWEEN_ARBITRAGE = 30  # 套利最小间隔（秒）

# 执行配置
MAX_EXECUTION_TIME_PER_LEG = 10  # 单腿最大执行时间（秒）
MAX_TOTAL_EXECUTION_TIME = 30  # 总执行最大时间（秒）
MAX_SLIPPAGE_TOLERANCE = 0.2  # 最大滑点容忍度（%）
ENABLE_ATOMIC_EXECUTION = True  # 是否启用原子化执行（失败自动回滚）

# 订单簿深度要求
MIN_ORDERBOOK_DEPTH_MULTIPLIER = 3.0  # 订单簿深度必须是交易量的倍数
MIN_ORDERBOOK_DEPTH_USDT = 5000  # 最小订单簿深度（USDT）

# 交易所健康检查
MAX_API_LATENCY_MS = 500  # 最大API延迟（毫秒）
MIN_EXCHANGE_UPTIME = 0.99  # 最小交易所可用性（99%）
EXCHANGE_HEALTH_CHECK_INTERVAL = 60  # 健康检查间隔（秒）

# 手续费配置
ARBITRAGE_FEE_RATES = {
    "bitget": {"maker": 0.0002, "taker": 0.0006},
    "binance": {"maker": 0.0002, "taker": 0.0004},
    "okx": {"maker": 0.0002, "taker": 0.0005},
}

# 通知配置
ENABLE_ARBITRAGE_NOTIFICATIONS = True  # 是否启用套利通知
NOTIFY_ON_OPPORTUNITY = False  # 是否通知发现机会
NOTIFY_ON_EXECUTION = True  # 是否通知执行开始
NOTIFY_ON_COMPLETION = True  # 是否通知执行完成
NOTIFY_ON_FAILURE = True  # 是否通知执行失败

# 日志配置
ARBITRAGE_LOG_LEVEL = "INFO"  # 套利日志级别
LOG_ALL_SPREADS = False  # 是否记录所有价差
LOG_ALL_OPPORTUNITIES = True  # 是否记录所有机会
LOG_ALL_EXECUTIONS = True  # 是否记录所有执行

# ==================== Phase 0: 特性开关（用于渐进式优化）====================

# AI异步化开关
ASYNC_AI_ENABLED = False  # 是否启用AI异步调用（避免阻塞交易链路）

# 数据库批量写入开关
DB_BATCH_WRITES_ENABLED = False  # 是否启用数据库批量写入

# ML强制轻量化开关
ML_FORCE_LITE = False  # 是否强制使用轻量级ML预测器（生产环境推荐）

# 配置拆分开关
CONFIG_SPLIT_ENABLED = False  # 是否启用配置拆分（从config/目录加载）

# ==================== 配置验证 ====================

def validate_config():
    """验证配置有效性"""
    errors = []

    if not EXCHANGE_CONFIG.get("api_key"):
        errors.append("缺少 API Key")
    
    if LEVERAGE < 1 or LEVERAGE > 125:
        errors.append(f"杠杆倍数无效: {LEVERAGE}")
    
    if STOP_LOSS_PERCENT <= 0 or STOP_LOSS_PERCENT > 0.5:
        errors.append(f"止损比例无效: {STOP_LOSS_PERCENT}")
    
    if TAKE_PROFIT_PERCENT <= 0:
        errors.append(f"止盈比例无效: {TAKE_PROFIT_PERCENT}")
    
    if not ENABLE_STRATEGIES:
        errors.append("未启用任何策略")
    
    for strategy in ENABLE_STRATEGIES:
        valid_strategies = [
            "bollinger_breakthrough", "bollinger_trend", "rsi_divergence", "macd_cross",
            "ema_cross", "kdj_cross", "adx_trend", "volume_breakout",
            "multi_timeframe", "grid", "composite_score"
        ]
        if strategy not in valid_strategies:
            errors.append(f"未知策略: {strategy}")

    # 验证定期报告配置
    if ENABLE_PERIODIC_REPORT:
        if not isinstance(PERIODIC_REPORT_INTERVAL, int):
            errors.append("PERIODIC_REPORT_INTERVAL 必须是整数")
        elif PERIODIC_REPORT_INTERVAL < 30:
            errors.append("PERIODIC_REPORT_INTERVAL 不能小于30分钟")
        elif PERIODIC_REPORT_INTERVAL > 720:
            errors.append("PERIODIC_REPORT_INTERVAL 不能大于720分钟（12小时）")

        if PERIODIC_REPORT_DETAIL_LEVEL not in ['simple', 'standard', 'detailed']:
            errors.append("PERIODIC_REPORT_DETAIL_LEVEL 必须是 'simple', 'standard' 或 'detailed'")

        # 检查飞书配置
        if not ENABLE_FEISHU:
            errors.append("启用定期报告需要启用飞书通知 (ENABLE_FEISHU=True)")
        elif not FEISHU_WEBHOOK_URL:
            errors.append("启用定期报告需要配置飞书 Webhook URL")

    # 验证状态监控配置
    if ENABLE_STATUS_MONITOR:
        if not isinstance(STATUS_MONITOR_INTERVAL, int):
            errors.append("STATUS_MONITOR_INTERVAL 必须是整数")
        elif STATUS_MONITOR_INTERVAL < 1:
            errors.append("STATUS_MONITOR_INTERVAL 不能小于1分钟")
        elif STATUS_MONITOR_INTERVAL > 60:
            errors.append("STATUS_MONITOR_INTERVAL 不能大于60分钟")

        # 检查飞书配置
        if not ENABLE_FEISHU:
            errors.append("启用状态监控需要启用飞书通知 (ENABLE_FEISHU=True)")
        elif not FEISHU_WEBHOOK_URL:
            errors.append("启用状态监控需要配置飞书 Webhook URL")

        # 检查邮件配置（如果启用了邮件预警）
        if STATUS_MONITOR_EMAIL_ON_FAILURE:
            if not ENABLE_EMAIL:
                errors.append("启用邮件预警需要启用邮件通知 (ENABLE_EMAIL=True)")
            elif not EMAIL_SENDER or not EMAIL_RECEIVER:
                errors.append("启用邮件预警需要配置邮件发送者和接收者")

    # 验证Claude定时分析配置
    if ENABLE_CLAUDE_PERIODIC_ANALYSIS:
        if not isinstance(CLAUDE_PERIODIC_INTERVAL, int):
            errors.append("CLAUDE_PERIODIC_INTERVAL 必须是整数")
        elif CLAUDE_PERIODIC_INTERVAL < 10:
            errors.append("CLAUDE_PERIODIC_INTERVAL 不能小于10分钟")
        elif CLAUDE_PERIODIC_INTERVAL > 360:
            errors.append("CLAUDE_PERIODIC_INTERVAL 不能大于360分钟（6小时）")

        if CLAUDE_ANALYSIS_DETAIL_LEVEL not in ['simple', 'standard', 'detailed']:
            errors.append("CLAUDE_ANALYSIS_DETAIL_LEVEL 必须是 'simple', 'standard' 或 'detailed'")

        # 检查Claude配置
        if not ENABLE_CLAUDE_ANALYSIS:
            errors.append("启用Claude定时分析需要启用Claude分析 (ENABLE_CLAUDE_ANALYSIS=True)")
        elif not CLAUDE_API_KEY:
            errors.append("启用Claude定时分析需要配置Claude API Key")

        # 检查飞书配置（如果启用了飞书推送）
        if CLAUDE_PUSH_TO_FEISHU:
            if not ENABLE_FEISHU:
                errors.append("Claude分析推送到飞书需要启用飞书通知 (ENABLE_FEISHU=True)")
            elif not FEISHU_WEBHOOK_URL:
                errors.append("Claude分析推送到飞书需要配置飞书 Webhook URL")

    return errors


def print_config():
    """打印当前配置"""
    print("=" * 50)
    print("当前配置")
    print("=" * 50)
    print(f"交易对: {SYMBOL}")
    print(f"时间周期: {TIMEFRAME}")
    print(f"杠杆: {LEVERAGE}x")
    print(f"保证金模式: {MARGIN_MODE}")
    print(f"仓位比例: {POSITION_SIZE_PERCENT:.0%}")
    print(f"止损: {STOP_LOSS_PERCENT:.1%}")
    print(f"止盈: {TAKE_PROFIT_PERCENT:.1%}")
    print(f"策略: {ENABLE_STRATEGIES}")
    print(f"Kelly公式: {'启用' if USE_KELLY_CRITERION else '禁用'}")
    print(f"ATR止损: {'启用' if USE_ATR_STOP_LOSS else '禁用'}")
    print(f"分批建仓: {'启用' if USE_PARTIAL_POSITION else '禁用'}")
    print(f"多时间周期: {'启用' if MULTI_TIMEFRAME_ENABLED else '禁用'}")
    print("=" * 50)


if __name__ == "__main__":
    errors = validate_config()
    if errors:
        print("配置错误:")
        for e in errors:
            print(f"  - {e}")
    else:
        print_config()


# ==================== 导出 settings 对象 ====================
# 为了向后兼容，将当前模块作为 settings 对象导出
import sys
settings = sys.modules[__name__]

