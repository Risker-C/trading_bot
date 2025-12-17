"""
配置文件 - 增强版
整合 Qbot 功能后的完整配置
"""
import os
from typing import List, Dict
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ==================== 交易所配置 ====================

EXCHANGE_CONFIG = {
    "apiKey": os.getenv("BITGET_API_KEY", ""),
    "secret": os.getenv("BITGET_API_SECRET") or os.getenv("BITGET_SECRET", ""),
    "password": os.getenv("BITGET_API_PASSWORD") or os.getenv("BITGET_PASSWORD", ""),
}

SYMBOL = "BTCUSDT"
PRODUCT_TYPE = "USDT-FUTURES"  # USDT 合约
TIMEFRAME = "15m"              # 主时间周期
KLINE_LIMIT = 200              # K线数量

# ==================== 多时间周期配置（新增）====================

MULTI_TIMEFRAME_ENABLED = True
TIMEFRAMES = ["5m", "15m", "1h", "4h"]
TIMEFRAME_WEIGHTS = {
    "5m": 0.15,
    "15m": 0.30,
    "1h": 0.35,
    "4h": 0.20,
}

# ==================== 杠杆和保证金 ====================

LEVERAGE = 10
MARGIN_MODE = "crossed"  # isolated / crossed

# ==================== 仓位管理 ====================

POSITION_SIZE_PERCENT = 0.1   # 基础仓位比例（10%）
MIN_ORDER_USDT = 10            # 最小订单金额
MAX_ORDER_USDT = 1000          # 最大订单金额

# 分批建仓配置（新增）
USE_PARTIAL_POSITION = True    # 是否分批建仓
POSITION_PARTS = 3             # 分几批建仓
POSITION_ENTRY_TYPE = "pyramid"  # pyramid / equal / reverse_pyramid

# ==================== Kelly 公式配置（新增）====================

USE_KELLY_CRITERION = True     # 是否使用 Kelly 公式
KELLY_FRACTION = 0.5           # Kelly 分数（更保守）
MIN_WIN_RATE_FOR_KELLY = 0.4   # 使用 Kelly 的最低胜率要求

# ==================== 波动率配置（新增）====================

REDUCE_SIZE_ON_HIGH_VOL = True        # 高波动时减仓
HIGH_VOLATILITY_THRESHOLD = 0.03      # 高波动阈值（3%）
LOW_VOLATILITY_THRESHOLD = 0.01       # 低波动阈值（1%）
VOLATILITY_SIZE_FACTOR = 0.7          # 高波动时仓位系数
VOLATILITY_LOOKBACK = 20              # 波动率计算周期

# ==================== 止损止盈配置 ====================

STOP_LOSS_PERCENT = 0.02       # 止损比例 2%
TAKE_PROFIT_PERCENT = 0.04     # 止盈比例 4%
TRAILING_STOP_PERCENT = 0.015  # 移动止损回撤比例 1.5%

# ATR 动态止损（新增）
USE_ATR_STOP_LOSS = True       # 是否使用 ATR 止损
ATR_STOP_MULTIPLIER = 2.0      # ATR 倍数

# 分批止盈（新增）
USE_PARTIAL_TAKE_PROFIT = True # 是否分批止盈

# ==================== 策略配置 ====================

ENABLE_STRATEGIES: List[str] = [
    "bollinger_breakthrough",
    "rsi_divergence",
    "macd_cross",
    "ema_cross",
    "composite_score",
]

# 共识信号配置（新增）
USE_CONSENSUS_SIGNAL = True        # 是否使用共识信号
MIN_STRATEGY_AGREEMENT = 0.6       # 最小策略一致性
MIN_SIGNAL_STRENGTH = 0.5          # 最小信号强度
MIN_SIGNAL_CONFIDENCE = 0.5        # 最小置信度

# 动态策略选择配置（新增）
USE_DYNAMIC_STRATEGY = True        # 启用市场状态感知的动态策略选择
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
TRANSITIONING_CONFIDENCE_THRESHOLD = 0.4  # 过渡市置信度阈值

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

DB_PATH = "trading_bot.db"
LOG_DIR = "logs"
LOG_FILE = "trading_bot.log"       # 新增
LOG_LEVEL = "DEBUG"
SAVE_EQUITY_CURVE = True

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
STATUS_MONITOR_INTERVAL = 5  # 默认5分钟

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

# ==================== Claude AI 分析配置（新增）====================

# 是否启用 Claude AI 分析
ENABLE_CLAUDE_ANALYSIS = True  # 已启用

# Claude API配置（从环境变量读取）
CLAUDE_API_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")  # 使用ANTHROPIC_AUTH_TOKEN
CLAUDE_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")  # 自定义API端点

# Claude 模型选择
# 可选: claude-opus-4-5-20251101 (最强), claude-sonnet-4-5-20250929 (平衡), claude-haiku-4-20250514 (快速)
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# Claude 分析的最小信号强度阈值（低于此值不调用 Claude）
CLAUDE_MIN_SIGNAL_STRENGTH = 0.3

# Claude 分析超时时间（秒）
CLAUDE_TIMEOUT = 30  # 增加到30秒,避免API调用阻塞

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
ENABLE_CLAUDE_PERIODIC_ANALYSIS = True

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
ENABLE_CLAUDE_DAILY_REPORT = True

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
ENABLE_POLICY_LAYER = True

# Policy Layer 更新间隔（分钟）
# Claude 会定期分析交易上下文并更新策略参数
POLICY_UPDATE_INTERVAL = 30  # 默认30分钟

# Policy Layer 模式
# "shadow": 影子模式（只记录不生效，用于观察）
# "active": 主动模式（真实影响交易参数）
POLICY_LAYER_MODE = "shadow"  # 建议先用 "shadow" 观察1-2天

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
ENABLE_EXECUTION_FILTER = True

# 点差阈值（超过此值拒绝交易）
MAX_SPREAD_PCT = 0.001  # 0.1%

# 滑点阈值
MAX_SLIPPAGE_PCT = 0.002  # 0.2%

# 最小成交量比率（低于此值拒绝交易）
MIN_VOLUME_RATIO = 0.5  # 50%

# ATR突增阈值（超过此倍数延迟进场）
ATR_SPIKE_THRESHOLD = 1.5  # 1.5倍

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


# ==================== 配置验证 ====================

def validate_config():
    """验证配置有效性"""
    errors = []
    
    if not EXCHANGE_CONFIG["apiKey"]:
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
            "bollinger_breakthrough", "rsi_divergence", "macd_cross",
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

