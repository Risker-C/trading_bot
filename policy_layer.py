"""
Policy Layer - Claude AI 策略治理层

这是 Claude 与真实交易之间的"防火墙"层，负责：
1. 接收 Claude 的分析输出
2. 校验其合法性与边界
3. 决定是否生效
4. 将结果映射为策略参数和风控参数

核心原则：
- Claude 永远不能直接下单
- 所有参数变更必须可追溯、可回滚
- 参数只能在合理区间内变化
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

import config
from logger_utils import get_logger

logger = get_logger("policy_layer")


# ==================== 枚举定义 ====================

class MarketRegime(Enum):
    """市场制度"""
    TREND = "trend"              # 趋势市
    MEAN_REVERT = "mean_revert"  # 均值回归/震荡市
    CHOP = "chop"                # 混乱市
    UNKNOWN = "unknown"          # 未知


class RiskMode(Enum):
    """风控模式"""
    NORMAL = "normal"        # 正常模式
    DEFENSIVE = "defensive"  # 防守模式（连续亏损后）
    RECOVERY = "recovery"    # 恢复模式（从防守恢复中）
    AGGRESSIVE = "aggressive"  # 激进模式（连续盈利后）


class PolicyAction(Enum):
    """策略动作"""
    ENABLE_STRATEGY = "enable_strategy"
    DISABLE_STRATEGY = "disable_strategy"
    ADJUST_STOP_LOSS = "adjust_stop_loss"
    ADJUST_TAKE_PROFIT = "adjust_take_profit"
    ADJUST_POSITION_SIZE = "adjust_position_size"
    SWITCH_RISK_MODE = "switch_risk_mode"
    ENABLE_TRAILING_STOP = "enable_trailing_stop"
    DISABLE_TRAILING_STOP = "disable_trailing_stop"


# ==================== 数据类定义 ====================

@dataclass
class TradingContext:
    """交易上下文 - Claude 分析所需的完整信息"""

    # A. 历史交易状态（系统状态）
    recent_trades_count: int = 0
    win_rate: float = 0.0
    recent_pnl: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    # B. 当前持仓状态（仓位状态）
    has_position: bool = False
    position_side: Optional[str] = None  # long/short
    position_amount: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    holding_time_minutes: float = 0.0
    current_stop_loss: float = 0.0
    current_take_profit: float = 0.0

    # C. 实时市场结构（行情状态）
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    trend_direction: int = 0  # 1=上涨, -1=下跌, 0=震荡
    volatility: float = 0.0
    adx: float = 0.0
    volume_ratio: float = 0.0

    # D. 系统状态
    current_risk_mode: RiskMode = RiskMode.NORMAL
    daily_pnl: float = 0.0
    daily_trades: int = 0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'recent_trades_count': self.recent_trades_count,
            'win_rate': self.win_rate,
            'recent_pnl': self.recent_pnl,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'has_position': self.has_position,
            'position_side': self.position_side,
            'position_amount': self.position_amount,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'holding_time_minutes': self.holding_time_minutes,
            'current_stop_loss': self.current_stop_loss,
            'current_take_profit': self.current_take_profit,
            'market_regime': self.market_regime.value,
            'trend_direction': self.trend_direction,
            'volatility': self.volatility,
            'adx': self.adx,
            'volume_ratio': self.volume_ratio,
            'current_risk_mode': self.current_risk_mode.value,
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
        }


@dataclass
class PolicyDecision:
    """策略决策 - Claude 输出的参数建议"""

    # 市场制度判断
    regime: MarketRegime = MarketRegime.UNKNOWN
    regime_confidence: float = 0.0

    # 风控模式建议
    suggested_risk_mode: Optional[RiskMode] = None

    # 止损止盈调整建议
    suggested_stop_loss_pct: Optional[float] = None  # 建议的止损百分比
    suggested_take_profit_pct: Optional[float] = None  # 建议的止盈百分比
    suggested_trailing_stop_pct: Optional[float] = None  # 建议的移动止损百分比
    enable_trailing_stop: Optional[bool] = None  # 是否启用移动止损

    # 仓位调整建议
    suggested_position_multiplier: Optional[float] = None  # 仓位倍数（0.5-2.0）

    # 策略启停建议
    strategies_to_enable: List[str] = field(default_factory=list)
    strategies_to_disable: List[str] = field(default_factory=list)

    # 决策元数据
    confidence: float = 0.0
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    ttl_minutes: int = 30  # 生效时长（分钟）

    # 原始 Claude 响应
    raw_claude_response: Optional[Dict] = None

    def is_expired(self) -> bool:
        """检查决策是否过期"""
        elapsed = datetime.now() - self.timestamp
        return elapsed.total_seconds() > self.ttl_minutes * 60

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'regime': self.regime.value,
            'regime_confidence': self.regime_confidence,
            'suggested_risk_mode': self.suggested_risk_mode.value if self.suggested_risk_mode else None,
            'suggested_stop_loss_pct': self.suggested_stop_loss_pct,
            'suggested_take_profit_pct': self.suggested_take_profit_pct,
            'suggested_trailing_stop_pct': self.suggested_trailing_stop_pct,
            'enable_trailing_stop': self.enable_trailing_stop,
            'suggested_position_multiplier': self.suggested_position_multiplier,
            'strategies_to_enable': self.strategies_to_enable,
            'strategies_to_disable': self.strategies_to_disable,
            'confidence': self.confidence,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'ttl_minutes': self.ttl_minutes,
        }


@dataclass
class PolicyParameters:
    """当前生效的策略参数"""

    # 止损止盈参数
    stop_loss_pct: float = field(default_factory=lambda: config.STOP_LOSS_PERCENT)
    take_profit_pct: float = field(default_factory=lambda: config.TAKE_PROFIT_PERCENT)
    trailing_stop_pct: float = field(default_factory=lambda: config.TRAILING_STOP_PERCENT)
    trailing_stop_enabled: bool = True

    # 仓位参数
    position_size_multiplier: float = 1.0

    # 策略启用状态
    enabled_strategies: List[str] = field(default_factory=lambda: config.ENABLE_STRATEGIES.copy())

    # 风控模式
    risk_mode: RiskMode = RiskMode.NORMAL

    # 参数来源
    last_update_time: datetime = field(default_factory=datetime.now)
    last_decision: Optional[PolicyDecision] = None

    def reset_to_default(self):
        """重置为默认配置"""
        self.stop_loss_pct = config.STOP_LOSS_PERCENT
        self.take_profit_pct = config.TAKE_PROFIT_PERCENT
        self.trailing_stop_pct = config.TRAILING_STOP_PERCENT
        self.trailing_stop_enabled = True
        self.position_size_multiplier = 1.0
        self.enabled_strategies = config.ENABLE_STRATEGIES.copy()
        self.risk_mode = RiskMode.NORMAL
        self.last_update_time = datetime.now()
        logger.info("策略参数已重置为默认值")


# ==================== Policy Layer 核心类 ====================

class PolicyLayer:
    """
    策略治理层

    职责：
    1. 接收 Claude 的分析输出
    2. 校验其合法性与边界
    3. 决定是否生效
    4. 将结果映射为策略参数和风控参数
    """

    def __init__(self):
        """初始化 Policy Layer"""
        self.current_params = PolicyParameters()
        self.decision_history: List[PolicyDecision] = []

        # 参数边界约束
        self.param_bounds = {
            'stop_loss_pct': (0.005, 0.05),      # 0.5% - 5%
            'take_profit_pct': (0.01, 0.10),     # 1% - 10%
            'trailing_stop_pct': (0.005, 0.03),  # 0.5% - 3%
            'position_multiplier': (0.3, 2.0),   # 0.3x - 2.0x
        }

        # 风控模式参数映射
        self.risk_mode_params = {
            RiskMode.NORMAL: {
                'stop_loss_multiplier': 1.0,
                'take_profit_multiplier': 1.0,
                'position_multiplier': 1.0,
            },
            RiskMode.DEFENSIVE: {
                'stop_loss_multiplier': 0.7,  # 更紧的止损
                'take_profit_multiplier': 0.8,  # 更快止盈
                'position_multiplier': 0.5,  # 减半仓位
            },
            RiskMode.RECOVERY: {
                'stop_loss_multiplier': 0.85,
                'take_profit_multiplier': 0.9,
                'position_multiplier': 0.7,
            },
            RiskMode.AGGRESSIVE: {
                'stop_loss_multiplier': 1.2,  # 更宽的止损
                'take_profit_multiplier': 1.5,  # 更高的止盈
                'position_multiplier': 1.3,  # 增加仓位
            },
        }

        logger.info("Policy Layer 初始化成功")

    def validate_and_apply_decision(
        self,
        decision: PolicyDecision,
        context: TradingContext
    ) -> Tuple[bool, str, List[PolicyAction]]:
        """
        验证并应用 Claude 的决策

        Args:
            decision: Claude 的策略决策
            context: 当前交易上下文

        Returns:
            (是否应用成功, 原因, 应用的动作列表)
        """
        if decision.is_expired():
            return False, "决策已过期", []

        if decision.confidence < 0.3:
            return False, f"置信度过低: {decision.confidence:.2f}", []

        applied_actions = []

        # 1. 验证并应用止损调整
        if decision.suggested_stop_loss_pct is not None:
            success, action = self._apply_stop_loss_adjustment(
                decision.suggested_stop_loss_pct,
                context
            )
            if success:
                applied_actions.append(action)

        # 2. 验证并应用止盈调整
        if decision.suggested_take_profit_pct is not None:
            success, action = self._apply_take_profit_adjustment(
                decision.suggested_take_profit_pct,
                context
            )
            if success:
                applied_actions.append(action)

        # 3. 验证并应用移动止损调整
        if decision.suggested_trailing_stop_pct is not None:
            success, action = self._apply_trailing_stop_adjustment(
                decision.suggested_trailing_stop_pct,
                decision.enable_trailing_stop,
                context
            )
            if success:
                applied_actions.append(action)

        # 4. 验证并应用仓位调整
        if decision.suggested_position_multiplier is not None:
            success, action = self._apply_position_adjustment(
                decision.suggested_position_multiplier,
                context
            )
            if success:
                applied_actions.append(action)

        # 5. 验证并应用风控模式切换
        if decision.suggested_risk_mode is not None:
            success, action = self._apply_risk_mode_switch(
                decision.suggested_risk_mode,
                context
            )
            if success:
                applied_actions.append(action)

        # 6. 验证并应用策略启停
        if decision.strategies_to_enable or decision.strategies_to_disable:
            success, actions = self._apply_strategy_control(
                decision.strategies_to_enable,
                decision.strategies_to_disable,
                context
            )
            if success:
                applied_actions.extend(actions)

        # 记录决策
        self.current_params.last_decision = decision
        self.current_params.last_update_time = datetime.now()
        self.decision_history.append(decision)

        # 限制历史记录长度
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]

        if applied_actions:
            logger.info(f"✅ Policy 决策已应用: {len(applied_actions)} 个动作")
            logger.info(f"   原因: {decision.reason}")
            for action in applied_actions:
                logger.info(f"   - {action.value}")
            return True, decision.reason, applied_actions
        else:
            return False, "没有可应用的参数调整", []

    def _apply_stop_loss_adjustment(
        self,
        suggested_pct: float,
        context: TradingContext
    ) -> Tuple[bool, Optional[PolicyAction]]:
        """应用止损调整"""
        min_sl, max_sl = self.param_bounds['stop_loss_pct']

        # 边界检查
        if suggested_pct < min_sl or suggested_pct > max_sl:
            logger.warning(f"止损建议 {suggested_pct:.2%} 超出边界 [{min_sl:.2%}, {max_sl:.2%}]")
            suggested_pct = max(min_sl, min(max_sl, suggested_pct))

        # 变化幅度检查（单次调整不超过 50%）
        current_sl = self.current_params.stop_loss_pct
        max_change = current_sl * 0.5
        if abs(suggested_pct - current_sl) > max_change:
            logger.warning(f"止损调整幅度过大，限制在 ±50%")
            if suggested_pct > current_sl:
                suggested_pct = current_sl + max_change
            else:
                suggested_pct = current_sl - max_change

        # 应用调整
        old_value = self.current_params.stop_loss_pct
        self.current_params.stop_loss_pct = suggested_pct

        logger.info(f"📊 止损调整: {old_value:.2%} → {suggested_pct:.2%}")
        return True, PolicyAction.ADJUST_STOP_LOSS

    def _apply_take_profit_adjustment(
        self,
        suggested_pct: float,
        context: TradingContext
    ) -> Tuple[bool, Optional[PolicyAction]]:
        """应用止盈调整"""
        min_tp, max_tp = self.param_bounds['take_profit_pct']

        # 边界检查
        if suggested_pct < min_tp or suggested_pct > max_tp:
            logger.warning(f"止盈建议 {suggested_pct:.2%} 超出边界 [{min_tp:.2%}, {max_tp:.2%}]")
            suggested_pct = max(min_tp, min(max_tp, suggested_pct))

        # 确保止盈 > 止损
        if suggested_pct <= self.current_params.stop_loss_pct:
            logger.warning(f"止盈 {suggested_pct:.2%} 必须大于止损 {self.current_params.stop_loss_pct:.2%}")
            suggested_pct = self.current_params.stop_loss_pct * 1.5

        # 应用调整
        old_value = self.current_params.take_profit_pct
        self.current_params.take_profit_pct = suggested_pct

        logger.info(f"📊 止盈调整: {old_value:.2%} → {suggested_pct:.2%}")
        return True, PolicyAction.ADJUST_TAKE_PROFIT

    def _apply_trailing_stop_adjustment(
        self,
        suggested_pct: Optional[float],
        enable: Optional[bool],
        context: TradingContext
    ) -> Tuple[bool, Optional[PolicyAction]]:
        """应用移动止损调整"""
        action = None

        # 调整移动止损百分比
        if suggested_pct is not None:
            min_ts, max_ts = self.param_bounds['trailing_stop_pct']

            if suggested_pct < min_ts or suggested_pct > max_ts:
                logger.warning(f"移动止损建议 {suggested_pct:.2%} 超出边界 [{min_ts:.2%}, {max_ts:.2%}]")
                suggested_pct = max(min_ts, min(max_ts, suggested_pct))

            old_value = self.current_params.trailing_stop_pct
            self.current_params.trailing_stop_pct = suggested_pct
            logger.info(f"📊 移动止损调整: {old_value:.2%} → {suggested_pct:.2%}")
            action = PolicyAction.ADJUST_STOP_LOSS

        # 启用/禁用移动止损
        if enable is not None:
            old_state = self.current_params.trailing_stop_enabled
            self.current_params.trailing_stop_enabled = enable

            if enable != old_state:
                logger.info(f"📊 移动止损: {'启用' if enable else '禁用'}")
                action = PolicyAction.ENABLE_TRAILING_STOP if enable else PolicyAction.DISABLE_TRAILING_STOP

        return action is not None, action

    def _apply_position_adjustment(
        self,
        suggested_multiplier: float,
        context: TradingContext
    ) -> Tuple[bool, Optional[PolicyAction]]:
        """应用仓位调整"""
        min_mult, max_mult = self.param_bounds['position_multiplier']

        # 边界检查
        if suggested_multiplier < min_mult or suggested_multiplier > max_mult:
            logger.warning(f"仓位倍数建议 {suggested_multiplier:.2f} 超出边界 [{min_mult:.2f}, {max_mult:.2f}]")
            suggested_multiplier = max(min_mult, min(max_mult, suggested_multiplier))

        # 应用调整
        old_value = self.current_params.position_size_multiplier
        self.current_params.position_size_multiplier = suggested_multiplier

        logger.info(f"📊 仓位倍数调整: {old_value:.2f}x → {suggested_multiplier:.2f}x")
        return True, PolicyAction.ADJUST_POSITION_SIZE

    def _apply_risk_mode_switch(
        self,
        suggested_mode: RiskMode,
        context: TradingContext
    ) -> Tuple[bool, Optional[PolicyAction]]:
        """应用风控模式切换"""
        old_mode = self.current_params.risk_mode

        if old_mode == suggested_mode:
            return False, None

        # 应用风控模式
        self.current_params.risk_mode = suggested_mode

        # 根据风控模式调整参数
        mode_params = self.risk_mode_params[suggested_mode]

        # 调整止损
        base_sl = config.STOP_LOSS_PERCENT
        self.current_params.stop_loss_pct = base_sl * mode_params['stop_loss_multiplier']

        # 调整止盈
        base_tp = config.TAKE_PROFIT_PERCENT
        self.current_params.take_profit_pct = base_tp * mode_params['take_profit_multiplier']

        # 调整仓位
        self.current_params.position_size_multiplier = mode_params['position_multiplier']

        logger.info(f"🔄 风控模式切换: {old_mode.value} → {suggested_mode.value}")
        logger.info(f"   止损: {self.current_params.stop_loss_pct:.2%}")
        logger.info(f"   止盈: {self.current_params.take_profit_pct:.2%}")
        logger.info(f"   仓位: {self.current_params.position_size_multiplier:.2f}x")

        return True, PolicyAction.SWITCH_RISK_MODE

    def _apply_strategy_control(
        self,
        to_enable: List[str],
        to_disable: List[str],
        context: TradingContext
    ) -> Tuple[bool, List[PolicyAction]]:
        """应用策略启停控制"""
        actions = []

        # 启用策略
        for strategy in to_enable:
            if strategy not in self.current_params.enabled_strategies:
                self.current_params.enabled_strategies.append(strategy)
                logger.info(f"✅ 启用策略: {strategy}")
                actions.append(PolicyAction.ENABLE_STRATEGY)

        # 禁用策略
        for strategy in to_disable:
            if strategy in self.current_params.enabled_strategies:
                self.current_params.enabled_strategies.remove(strategy)
                logger.info(f"❌ 禁用策略: {strategy}")
                actions.append(PolicyAction.DISABLE_STRATEGY)

        # 确保至少有一个策略启用
        if not self.current_params.enabled_strategies:
            logger.warning("⚠️ 所有策略被禁用，恢复默认策略")
            self.current_params.enabled_strategies = config.ENABLE_STRATEGIES.copy()
            return False, []

        return len(actions) > 0, actions

    def get_current_parameters(self) -> PolicyParameters:
        """获取当前生效的策略参数"""
        # 检查决策是否过期
        if self.current_params.last_decision and self.current_params.last_decision.is_expired():
            logger.info("⏰ Policy 决策已过期，重置为默认参数")
            self.current_params.reset_to_default()

        return self.current_params

    def get_stop_loss_percent(self) -> float:
        """获取当前止损百分比"""
        return self.get_current_parameters().stop_loss_pct

    def get_take_profit_percent(self) -> float:
        """获取当前止盈百分比"""
        return self.get_current_parameters().take_profit_pct

    def get_trailing_stop_percent(self) -> float:
        """获取当前移动止损百分比"""
        return self.get_current_parameters().trailing_stop_pct

    def is_trailing_stop_enabled(self) -> bool:
        """移动止损是否启用"""
        return self.get_current_parameters().trailing_stop_enabled

    def get_position_size_multiplier(self) -> float:
        """获取当前仓位倍数"""
        return self.get_current_parameters().position_size_multiplier

    def get_enabled_strategies(self) -> List[str]:
        """获取当前启用的策略列表"""
        return self.get_current_parameters().enabled_strategies.copy()

    def get_risk_mode(self) -> RiskMode:
        """获取当前风控模式"""
        return self.get_current_parameters().risk_mode

    def force_reset(self):
        """强制重置为默认参数"""
        self.current_params.reset_to_default()
        logger.warning("🔄 Policy Layer 已强制重置")

    def get_status_report(self) -> Dict:
        """获取状态报告"""
        params = self.get_current_parameters()

        return {
            'current_parameters': {
                'stop_loss_pct': f"{params.stop_loss_pct:.2%}",
                'take_profit_pct': f"{params.take_profit_pct:.2%}",
                'trailing_stop_pct': f"{params.trailing_stop_pct:.2%}",
                'trailing_stop_enabled': params.trailing_stop_enabled,
                'position_multiplier': f"{params.position_size_multiplier:.2f}x",
                'risk_mode': params.risk_mode.value,
                'enabled_strategies': params.enabled_strategies,
            },
            'last_update': params.last_update_time.isoformat() if params.last_update_time else None,
            'last_decision': params.last_decision.to_dict() if params.last_decision else None,
            'decision_history_count': len(self.decision_history),
        }


# ==================== 全局实例 ====================

_policy_layer: Optional[PolicyLayer] = None


def get_policy_layer() -> PolicyLayer:
    """获取 Policy Layer 单例"""
    global _policy_layer
    if _policy_layer is None:
        _policy_layer = PolicyLayer()
    return _policy_layer
