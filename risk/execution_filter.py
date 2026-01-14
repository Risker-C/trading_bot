"""
执行层风控模块
在信号通过策略和Claude分析后，进行最后的执行层检查
"""
from typing import Tuple, Dict, Optional, Deque
from datetime import datetime, timedelta
from collections import deque
import pandas as pd
import numpy as np
import time

import config
from utils.logger_utils import get_logger
from strategies.indicators import IndicatorCalculator
from risk.liquidity_validator import get_liquidity_validator

logger = get_logger("execution_filter")


class ExecutionFilter:
    """执行层风控过滤器"""

    def __init__(self):
        self.enabled = getattr(config, 'ENABLE_EXECUTION_FILTER', True)

        # 阈值配置
        self.max_spread_pct = getattr(config, 'MAX_SPREAD_PCT', 0.001)  # 0.1%
        self.max_slippage_pct = getattr(config, 'MAX_SLIPPAGE_PCT', 0.002)  # 0.2%
        self.min_volume_ratio = getattr(config, 'MIN_VOLUME_RATIO', 0.5)  # 50%
        self.atr_spike_threshold = getattr(config, 'ATR_SPIKE_THRESHOLD', 1.5)  # 1.5x

        # 价格稳定性检测配置
        self.price_stability_enabled = getattr(config, 'PRICE_STABILITY_ENABLED', True)
        self.price_stability_window = getattr(config, 'PRICE_STABILITY_WINDOW_SECONDS', 5.0)
        self.price_stability_threshold = getattr(config, 'PRICE_STABILITY_THRESHOLD_PCT', 0.5)

        # 价格历史记录 (timestamp, price)
        self.price_history: Deque[Tuple[float, float]] = deque()
        self.last_price_sample_time = 0.0

        # 流动性验证器
        self.liquidity_validator = get_liquidity_validator()

        # 历史记录
        self.last_check_time: Optional[datetime] = None
        self.rejection_count = 0

    def check_all(
        self,
        df: pd.DataFrame,
        current_price: float,
        ticker: Dict,
        indicators: Dict
    ) -> Tuple[bool, str, Dict]:
        """
        执行所有检查

        Args:
            df: K线数据
            current_price: 当前价格
            ticker: 行情数据（包含bid/ask）
            indicators: 技术指标

        Returns:
            (是否通过, 原因, 详细信息)
        """
        if not self.enabled:
            return True, "执行过滤未启用", {}

        details = {
            'spread_check': True,
            'slippage_check': True,
            'liquidity_check': True,
            'price_stability_check': True,
            'volatility_check': True,
        }

        # 1. 检查点差
        spread_pass, spread_reason, spread_pct = self._check_spread(ticker)
        details['spread_check'] = spread_pass
        details['spread_pct'] = spread_pct
        if not spread_pass:
            self.rejection_count += 1
            return False, spread_reason, details

        # 2. 检查流动性
        liquidity_pass, liquidity_reason = self._check_liquidity(indicators)
        details['liquidity_check'] = liquidity_pass
        details['volume_ratio'] = indicators.get('volume_ratio', 0)
        if not liquidity_pass:
            self.rejection_count += 1
            return False, liquidity_reason, details

        # 3. 检查价格稳定性（新增）
        if self.price_stability_enabled:
            stability_pass, stability_reason, stability_volatility = self._check_price_stability(current_price)
            details['price_stability_check'] = stability_pass
            details['price_volatility_pct'] = stability_volatility
            if not stability_pass:
                self.rejection_count += 1
                return False, stability_reason, details

        # 4. 检查波动率冲击
        volatility_pass, volatility_reason = self._check_volatility_spike(df, indicators)
        details['volatility_check'] = volatility_pass
        if not volatility_pass:
            self.rejection_count += 1
            return False, volatility_reason, details

        # 所有检查通过
        self.last_check_time = datetime.now()
        return True, "执行层检查通过", details

    def _check_spread(self, ticker: Dict) -> Tuple[bool, str, float]:
        """
        检查点差是否异常

        Args:
            ticker: 行情数据

        Returns:
            (是否通过, 原因, 点差百分比)
        """
        try:
            bid = ticker.get('bid')
            ask = ticker.get('ask')

            if not bid or not ask:
                # 如果没有bid/ask数据，使用last价格，假设点差为0
                logger.debug("没有bid/ask数据，跳过点差检查")
                return True, "无bid/ask数据", 0.0

            spread_pct = (ask - bid) / bid

            if spread_pct > self.max_spread_pct:
                return False, f"点差过大({spread_pct:.3%} > {self.max_spread_pct:.3%})", spread_pct

            return True, "点差正常", spread_pct

        except Exception as e:
            logger.error(f"检查点差失败: {e}")
            return True, "点差检查异常", 0.0

    def _check_liquidity(self, indicators: Dict) -> Tuple[bool, str]:
        """
        检查流动性

        Args:
            indicators: 技术指标（包含volume_ratio）

        Returns:
            (是否通过, 原因)
        """
        try:
            volume_ratio = indicators.get('volume_ratio', 1.0)

            if volume_ratio < self.min_volume_ratio:
                return False, f"流动性不足(量比={volume_ratio:.2f} < {self.min_volume_ratio:.2f})"

            return True, "流动性充足"

        except Exception as e:
            logger.error(f"检查流动性失败: {e}")
            return True, "流动性检查异常"

    def _check_price_stability(self, current_price: float) -> Tuple[bool, str, float]:
        """
        检查价格稳定性

        Args:
            current_price: 当前价格

        Returns:
            (是否通过, 原因, 波动率百分比)
        """
        try:
            now = time.time()

            # 记录价格样本
            sample_interval = getattr(config, 'PRICE_STABILITY_SAMPLE_INTERVAL', 1.0)
            if now - self.last_price_sample_time >= sample_interval:
                self.price_history.append((now, current_price))
                self.last_price_sample_time = now

                # 清理过期数据
                retention_window = self.price_stability_window * 4
                cutoff_time = now - retention_window
                while self.price_history and self.price_history[0][0] < cutoff_time:
                    self.price_history.popleft()

            # 检查是否有足够的历史数据
            if len(self.price_history) < 2:
                return True, "价格数据收集中", 0.0

            # 计算观察窗口内的数据
            window_cutoff = now - self.price_stability_window
            window_prices = [price for timestamp, price in self.price_history if timestamp >= window_cutoff]

            if len(window_prices) < 2:
                return True, "价格数据收集中", 0.0

            # 计算波动率: (max - min) / min * 100
            max_price = max(window_prices)
            min_price = min(window_prices)

            if min_price <= 0:
                return True, "价格数据异常", 0.0

            volatility_pct = (max_price - min_price) / min_price * 100

            # 检查是否超过阈值
            if volatility_pct > self.price_stability_threshold:
                # 价格不稳定，重置历史数据
                self.price_history.clear()
                return False, f"价格波动过大({volatility_pct:.2f}% > {self.price_stability_threshold:.2f}%)", volatility_pct

            return True, "价格稳定", volatility_pct

        except Exception as e:
            logger.error(f"检查价格稳定性失败: {e}")
            return True, "价格稳定性检查异常", 0.0

    def _check_volatility_spike(
        self,
        df: pd.DataFrame,
        indicators: Dict
    ) -> Tuple[bool, str]:
        """
        检查ATR是否突增

        Args:
            df: K线数据
            indicators: 技术指标

        Returns:
            (是否通过, 原因)
        """
        try:
            current_atr = indicators.get('atr', 0)

            if current_atr == 0:
                return True, "无ATR数据"

            # 计算平均ATR（过去20根K线）
            ind = IndicatorCalculator(df)
            atr_series = ind.atr(period=14)

            if len(atr_series) < 20:
                return True, "ATR数据不足"

            avg_atr = atr_series.iloc[-20:-1].mean()  # 排除当前K线

            if avg_atr == 0:
                return True, "平均ATR为0"

            atr_ratio = current_atr / avg_atr

            if atr_ratio > self.atr_spike_threshold:
                return False, f"ATR突增({atr_ratio:.2f}x > {self.atr_spike_threshold:.2f}x)，等待波动平稳"

            return True, "波动正常"

        except Exception as e:
            logger.error(f"检查波动率失败: {e}")
            return True, "波动率检查异常"

    def check_slippage(
        self,
        expected_price: float,
        actual_price: float
    ) -> Tuple[bool, str, float]:
        """
        检查实际成交价格的滑点

        Args:
            expected_price: 预期价格
            actual_price: 实际成交价格

        Returns:
            (是否通过, 原因, 滑点百分比)
        """
        try:
            slippage_pct = abs(actual_price - expected_price) / expected_price

            if slippage_pct > self.max_slippage_pct:
                return False, f"滑点过大({slippage_pct:.3%} > {self.max_slippage_pct:.3%})", slippage_pct

            return True, "滑点正常", slippage_pct

        except Exception as e:
            logger.error(f"检查滑点失败: {e}")
            return True, "滑点检查异常", 0.0

    def get_optimal_order_type(
        self,
        signal_strength: float,
        volatility: float,
        urgency: str = "normal"
    ) -> str:
        """
        根据信号强度和波动率选择最优订单类型

        Args:
            signal_strength: 信号强度 (0-1)
            volatility: 波动率
            urgency: 紧急程度 (low/normal/high)

        Returns:
            订单类型 (market/limit/reject)
        """
        # 极弱信号直接拒绝
        if signal_strength < 0.4:
            return "reject"

        # 高波动环境
        if volatility > 0.03:
            if signal_strength > 0.8 and urgency == "high":
                return "market"  # 强信号+高紧急度=市价单
            else:
                return "limit"   # 其他情况用限价单降低成本

        # 正常波动环境
        if signal_strength > 0.7:
            return "market"  # 强信号=市价单
        else:
            return "limit"   # 中等信号=限价单

    def should_delay_entry(
        self,
        df: pd.DataFrame,
        indicators: Dict,
        delay_bars: int = 2
    ) -> Tuple[bool, str]:
        """
        判断是否应该延迟进场

        Args:
            df: K线数据
            indicators: 技术指标
            delay_bars: 延迟K线数

        Returns:
            (是否延迟, 原因)
        """
        # 检查ATR突增
        volatility_pass, volatility_reason = self._check_volatility_spike(df, indicators)
        if not volatility_pass:
            return True, f"波动率异常，建议延迟{delay_bars}根K线后重新评估"

        # 检查流动性
        volume_ratio = indicators.get('volume_ratio', 1.0)
        if volume_ratio < 0.3:
            return True, f"流动性极低(量比={volume_ratio:.2f})，建议延迟进场"

        return False, "可以立即进场"

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'enabled': self.enabled,
            'rejection_count': self.rejection_count,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'thresholds': {
                'max_spread_pct': self.max_spread_pct,
                'max_slippage_pct': self.max_slippage_pct,
                'min_volume_ratio': self.min_volume_ratio,
                'atr_spike_threshold': self.atr_spike_threshold,
            }
        }


class PositionSizer:
    """仓位计算器 - 基于波动率和风险"""

    def __init__(self):
        self.base_position_pct = config.POSITION_SIZE_PERCENT
        self.target_volatility = getattr(config, 'TARGET_VOLATILITY', 0.02)  # 2%
        self.max_position_multiplier = getattr(config, 'MAX_POSITION_MULTIPLIER', 2.0)
        self.min_position_multiplier = getattr(config, 'MIN_POSITION_MULTIPLIER', 0.5)

    def calculate_volatility_adjusted_size(
        self,
        current_volatility: float,
        signal_strength: float = 1.0,
        consecutive_losses: int = 0
    ) -> float:
        """
        计算波动率调整后的仓位

        Args:
            current_volatility: 当前波动率
            signal_strength: 信号强度 (0-1)
            consecutive_losses: 连续亏损次数

        Returns:
            调整后的仓位比例
        """
        if current_volatility == 0:
            return self.base_position_pct

        # 1. 波动率调整
        volatility_factor = self.target_volatility / current_volatility
        volatility_factor = max(
            self.min_position_multiplier,
            min(self.max_position_multiplier, volatility_factor)
        )

        # 2. 信号强度调整
        strength_factor = 0.5 + (signal_strength * 0.5)  # 0.5-1.0

        # 3. 连续亏损调整
        loss_factor = self._get_loss_streak_multiplier(consecutive_losses)

        # 综合调整
        adjusted_size = self.base_position_pct * volatility_factor * strength_factor * loss_factor

        logger.debug(
            f"仓位计算: 基础={self.base_position_pct:.1%}, "
            f"波动率因子={volatility_factor:.2f}, "
            f"信号因子={strength_factor:.2f}, "
            f"亏损因子={loss_factor:.2f}, "
            f"最终={adjusted_size:.1%}"
        )

        return adjusted_size

    def _get_loss_streak_multiplier(self, consecutive_losses: int) -> float:
        """
        根据连续亏损次数获取仓位乘数

        Args:
            consecutive_losses: 连续亏损次数

        Returns:
            仓位乘数
        """
        if consecutive_losses >= 5:
            return 0.0  # 完全停止
        elif consecutive_losses >= 3:
            return 0.5  # 减半
        elif consecutive_losses >= 2:
            return 0.75  # 减少25%
        else:
            return 1.0  # 正常

    def calculate_kelly_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        kelly_fraction: float = 0.5
    ) -> float:
        """
        使用Kelly公式计算仓位

        Args:
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损
            kelly_fraction: Kelly分数（保守系数）

        Returns:
            Kelly仓位比例
        """
        if avg_loss == 0 or win_rate == 0:
            return self.base_position_pct

        # Kelly = W - (1-W)/R
        # W = 胜率, R = 平均盈利/平均亏损
        r = abs(avg_win / avg_loss)
        kelly = win_rate - (1 - win_rate) / r

        # 使用分数Kelly（更保守）
        kelly_size = max(0, kelly * kelly_fraction)

        # 限制最大仓位
        kelly_size = min(kelly_size, 0.25)

        return kelly_size


class DailyLossKillSwitch:
    """单日最大亏损熔断"""

    def __init__(self):
        self.max_daily_loss_pct = getattr(config, 'MAX_DAILY_LOSS_PCT', 0.05)  # 5%
        self.daily_pnl = 0.0
        self.initial_balance = 0.0
        self.last_reset_date = datetime.now().date()
        self.is_triggered = False

    def reset_daily(self, current_balance: float):
        """重置日统计"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            self.daily_pnl = 0.0
            self.initial_balance = current_balance
            self.last_reset_date = today
            self.is_triggered = False
            logger.info(f"重置日统计，初始余额: {current_balance:.2f}")

    def update_pnl(self, pnl: float):
        """更新日盈亏"""
        self.daily_pnl += pnl

    def should_stop_trading(self) -> Tuple[bool, str]:
        """检查是否触发熔断"""
        if self.is_triggered:
            return True, "单日亏损熔断已触发"

        if self.initial_balance == 0:
            return False, "正常"

        loss_pct = abs(self.daily_pnl) / self.initial_balance

        if self.daily_pnl < 0 and loss_pct >= self.max_daily_loss_pct:
            self.is_triggered = True
            return True, f"单日亏损达到{loss_pct:.1%}，触发熔断"

        return False, "正常"

    def get_remaining_loss_budget(self) -> float:
        """获取剩余亏损预算"""
        if self.initial_balance == 0:
            return 0.0

        max_loss = self.initial_balance * self.max_daily_loss_pct
        remaining = max_loss - abs(self.daily_pnl)
        return max(0, remaining)


# 全局实例
_execution_filter: Optional[ExecutionFilter] = None
_position_sizer: Optional[PositionSizer] = None
_kill_switch: Optional[DailyLossKillSwitch] = None


def get_execution_filter() -> ExecutionFilter:
    """获取执行过滤器单例"""
    global _execution_filter
    if _execution_filter is None:
        _execution_filter = ExecutionFilter()
    return _execution_filter


def get_position_sizer() -> PositionSizer:
    """获取仓位计算器单例"""
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()
    return _position_sizer


def get_kill_switch() -> DailyLossKillSwitch:
    """获取熔断器单例"""
    global _kill_switch
    if _kill_switch is None:
        _kill_switch = DailyLossKillSwitch()
    return _kill_switch
