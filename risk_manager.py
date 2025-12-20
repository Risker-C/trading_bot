"""
风险管理器 - 增强版
包含 Kelly 公式、动态止损、波动率调整等功能
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

import config
from indicators import calc_atr, calc_volatility
from logger_utils import get_logger, db

logger = get_logger("risk_manager")


# ==================== 数据类定义 ====================

@dataclass
class PositionInfo:
    """持仓信息"""
    side: str                          # long / short
    amount: float                      # 持仓数量
    entry_price: float                 # 开仓均价
    entry_time: datetime               # 开仓时间
    current_price: float = 0           # 当前价格
    highest_price: float = 0           # 持仓期间最高价
    lowest_price: float = 0            # 持仓期间最低价
    unrealized_pnl: float = 0          # 未实现盈亏
    unrealized_pnl_pct: float = 0      # 未实现盈亏百分比
    add_count: int = 0                 # 加仓次数
    partial_close_count: int = 0       # 部分平仓次数
    stop_loss_price: float = 0         # 止损价
    take_profit_price: float = 0       # 止盈价
    trailing_stop_price: float = 0     # 移动止损价

    # ===== 动态止盈相关字段 =====
    entry_fee: float = 0                    # 开仓手续费（USDT）
    recent_prices: List[float] = field(default_factory=list)  # 最近N次价格
    max_profit: float = 0                   # 最大浮动盈利（USDT）
    profit_threshold_reached: bool = False  # 是否达到盈利门槛
    trailing_take_profit_price: float = 0   # 动态止盈价格
    
    def update_price(self, current_price: float):
        """更新当前价格和极值"""
        self.current_price = current_price
        
        if self.highest_price == 0:
            self.highest_price = current_price
        else:
            self.highest_price = max(self.highest_price, current_price)
        
        if self.lowest_price == 0:
            self.lowest_price = current_price
        else:
            self.lowest_price = min(self.lowest_price, current_price)
        
        # 计算未实现盈亏
        if self.side == 'long':
            self.unrealized_pnl = (current_price - self.entry_price) * self.amount
            self.unrealized_pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.amount
            self.unrealized_pnl_pct = (self.entry_price - current_price) / self.entry_price * 100

    # ===== 动态止盈相关方法 =====

    def calculate_entry_fee(self, entry_price: float, amount: float) -> float:
        """
        计算开仓手续费

        Args:
            entry_price: 开仓价格
            amount: 持仓数量

        Returns:
            开仓手续费（USDT）
        """
        return entry_price * amount * config.TRADING_FEE_RATE

    def calculate_net_profit(self, current_price: float) -> float:
        """
        计算扣除手续费后的净盈利

        Args:
            current_price: 当前价格

        Returns:
            净盈利（USDT）
        """
        # 计算毛盈利
        if self.side == 'long':
            gross_profit = (current_price - self.entry_price) * self.amount
        else:
            gross_profit = (self.entry_price - current_price) * self.amount

        # 扣除开仓和平仓手续费
        close_fee = current_price * self.amount * config.TRADING_FEE_RATE
        net_profit = gross_profit - self.entry_fee - close_fee

        return net_profit

    def update_recent_prices(self, current_price: float):
        """
        更新最近N次价格

        Args:
            current_price: 当前价格
        """
        self.recent_prices.append(current_price)
        # 保持窗口大小
        if len(self.recent_prices) > config.TRAILING_TP_PRICE_WINDOW:
            self.recent_prices.pop(0)

    def get_price_average(self) -> float:
        """
        获取最近N次价格的均值

        Returns:
            价格均值，如果价格列表为空则返回0
        """
        if not self.recent_prices:
            return 0
        return sum(self.recent_prices) / len(self.recent_prices)


@dataclass
class RiskMetrics:
    """风险指标"""
    # 回撤相关
    current_drawdown: float = 0        # 当前回撤
    max_drawdown: float = 0            # 最大回撤
    peak_equity: float = 0             # 权益峰值
    
    # 胜率相关
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    
    # 盈亏相关
    total_pnl: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0           # 盈亏比
    expectancy: float = 0              # 期望值
    
    # 连续统计
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    
    # 波动率
    volatility: float = 0
    atr: float = 0
    atr_percent: float = 0
    
    # Kelly 公式
    kelly_fraction: float = 0
    optimal_position_size: float = 0
    
    def calculate_kelly(self):
        """计算 Kelly 公式最优仓位"""
        if self.total_trades < 10:
            self.kelly_fraction = 0
            return
        
        if self.avg_loss == 0:
            self.kelly_fraction = 0
            return
        
        # Kelly = W - (1-W)/R
        # W = 胜率, R = 平均盈利/平均亏损
        w = self.win_rate
        r = abs(self.avg_win / self.avg_loss) if self.avg_loss != 0 else 1
        
        kelly = w - (1 - w) / r
        
        # 使用分数 Kelly（更保守）
        self.kelly_fraction = max(0, kelly * config.KELLY_FRACTION)
        
        # 限制最大仓位
        self.kelly_fraction = min(self.kelly_fraction, 0.25)


@dataclass
class StopLossResult:
    """止损检查结果"""
    should_stop: bool = False
    stop_type: str = ""                # stop_loss / take_profit / trailing_stop / atr_stop
    reason: str = ""
    current_price: float = 0
    stop_price: float = 0
    pnl_percent: float = 0


# ==================== 风险管理器 ====================

class RiskManager:
    """风险管理器"""
    
    def __init__(self, trader=None):
        self.trader = trader
        self.position: Optional[PositionInfo] = None
        self.metrics = RiskMetrics()
        
        # 日内统计
        self.daily_loss = 0
        self.daily_trades = 0
        self.daily_pnl = 0
        
        # 交易控制
        self.last_trade_time: Optional[datetime] = None
        self.last_loss_time: Optional[datetime] = None
        self.trade_cooldown = 60  # 交易冷却时间（秒）
        self.loss_cooldown = 300  # 亏损后冷却时间（秒）
        
        # 历史记录
        self.trade_history: List[Dict] = []
        self.equity_curve: List[Dict] = []
        
        # 加载历史数据
        self._load_history()
    
    def _load_history(self):
        """加载历史交易数据计算指标"""
        try:
            trades = db.get_trades(limit=100)
            
            if not trades:
                return
            
            wins = []
            losses = []
            consecutive_loss = 0
            consecutive_win = 0
            
            for trade in trades:
                pnl = trade.get('pnl', 0)
                if pnl > 0:
                    wins.append(pnl)
                    consecutive_win += 1
                    consecutive_loss = 0
                elif pnl < 0:
                    losses.append(pnl)
                    consecutive_loss += 1
                    consecutive_win = 0
                
                self.metrics.max_consecutive_losses = max(
                    self.metrics.max_consecutive_losses, consecutive_loss
                )
                self.metrics.max_consecutive_wins = max(
                    self.metrics.max_consecutive_wins, consecutive_win
                )
            
            # 只计算有 PnL 的完成交易（排除开仓记录和 pnl=0 的记录）
            completed_trades = len(wins) + len(losses)
            self.metrics.total_trades = completed_trades
            self.metrics.winning_trades = len(wins)
            self.metrics.losing_trades = len(losses)
            self.metrics.win_rate = len(wins) / completed_trades if completed_trades > 0 else 0
            self.metrics.avg_win = sum(wins) / len(wins) if wins else 0
            self.metrics.avg_loss = sum(losses) / len(losses) if losses else 0
            self.metrics.total_pnl = sum(wins) + sum(losses)
            
            # 盈亏比
            if losses and sum(losses) != 0:
                self.metrics.profit_factor = abs(sum(wins) / sum(losses))
            
            # 期望值
            self.metrics.expectancy = (
                self.metrics.win_rate * self.metrics.avg_win +
                (1 - self.metrics.win_rate) * self.metrics.avg_loss
            )
            
            # 计算 Kelly
            self.metrics.calculate_kelly()
            
            logger.info(f"加载历史数据: {self.metrics.total_trades}笔交易, "
                       f"胜率={self.metrics.win_rate:.1%}, "
                       f"Kelly={self.metrics.kelly_fraction:.2%}")
            
        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")

    # ==================== Policy Layer 集成（新增）====================

    def get_policy_adjusted_stop_loss(self, entry_price: float, side: str, df: pd.DataFrame = None) -> float:
        """
        获取 Policy Layer 调整后的止损价格

        Args:
            entry_price: 入场价
            side: 方向 (long/short)
            df: K线数据

        Returns:
            止损价格
        """
        try:
            from policy_layer import get_policy_layer

            policy = get_policy_layer()
            stop_loss_pct = policy.get_stop_loss_percent()

            if side == 'long':
                return entry_price * (1 - stop_loss_pct / config.LEVERAGE)
            else:
                return entry_price * (1 + stop_loss_pct / config.LEVERAGE)

        except Exception as e:
            logger.error(f"获取 Policy 止损参数失败: {e}")
            # 失败时使用默认参数
            return self._calculate_fixed_stop_loss(entry_price, side)

    def get_policy_adjusted_take_profit(self, entry_price: float, side: str) -> float:
        """
        获取 Policy Layer 调整后的止盈价格

        Args:
            entry_price: 入场价
            side: 方向 (long/short)

        Returns:
            止盈价格
        """
        try:
            from policy_layer import get_policy_layer

            policy = get_policy_layer()
            take_profit_pct = policy.get_take_profit_percent()

            if side == 'long':
                return entry_price * (1 + take_profit_pct / config.LEVERAGE)
            else:
                return entry_price * (1 - take_profit_pct / config.LEVERAGE)

        except Exception as e:
            logger.error(f"获取 Policy 止盈参数失败: {e}")
            # 失败时使用默认参数
            if side == 'long':
                return entry_price * (1 + config.TAKE_PROFIT_PERCENT / config.LEVERAGE)
            else:
                return entry_price * (1 - config.TAKE_PROFIT_PERCENT / config.LEVERAGE)

    def get_policy_adjusted_position_size(self, base_amount: float) -> float:
        """
        获取 Policy Layer 调整后的仓位大小

        Args:
            base_amount: 基础仓位数量

        Returns:
            调整后的仓位数量
        """
        try:
            from policy_layer import get_policy_layer

            policy = get_policy_layer()
            multiplier = policy.get_position_size_multiplier()

            adjusted_amount = base_amount * multiplier
            logger.debug(f"Policy Layer 仓位调整: {base_amount:.6f} × {multiplier:.2f} = {adjusted_amount:.6f}")

            return adjusted_amount

        except Exception as e:
            logger.error(f"获取 Policy 仓位倍数失败: {e}")
            # 失败时返回原始仓位
            return base_amount

    # ==================== 仓位管理 ====================
    
    def calculate_position_size(
        self,
        balance: float,
        current_price: float,
        df: pd.DataFrame = None,
        signal_strength: float = 1.0
    ) -> float:
        """
        计算仓位大小
        综合考虑: Kelly公式、波动率、信号强度
        """
        if balance <= 0:
            return 0
        
        # 基础仓位比例
        base_ratio = config.POSITION_SIZE_PERCENT
        
        # 1. Kelly 公式调整
        if config.USE_KELLY_CRITERION and self.metrics.win_rate >= config.MIN_WIN_RATE_FOR_KELLY:
            if self.metrics.kelly_fraction > 0:
                kelly_ratio = self.metrics.kelly_fraction
                # 取 Kelly 和配置的较小值
                base_ratio = min(base_ratio, kelly_ratio)
                logger.debug(f"Kelly 建议仓位: {kelly_ratio:.2%}")
        
        # 2. 波动率调整
        if df is not None and config.REDUCE_SIZE_ON_HIGH_VOL:
            volatility = self._calculate_current_volatility(df)
            self.metrics.volatility = volatility
            
            if volatility > config.HIGH_VOLATILITY_THRESHOLD:
                # 高波动时减少仓位
                vol_factor = config.VOLATILITY_SIZE_FACTOR
                base_ratio *= vol_factor
                logger.debug(f"高波动率({volatility:.2%})，仓位系数: {vol_factor}")
            elif volatility < config.LOW_VOLATILITY_THRESHOLD:
                # 低波动时可适当增加
                vol_factor = min(1.2, 1 / volatility * config.LOW_VOLATILITY_THRESHOLD)
                base_ratio *= vol_factor
        
        # 3. 信号强度调整
        base_ratio *= signal_strength
        
        # 4. 连续亏损调整
        if self.metrics.consecutive_losses >= 3:
            loss_factor = max(0.5, 1 - self.metrics.consecutive_losses * 0.1)
            base_ratio *= loss_factor
            logger.warning(f"连续亏损{self.metrics.consecutive_losses}次，仓位降至{loss_factor:.0%}")
        
        # 5. 回撤调整
        if self.metrics.current_drawdown > 0.1:  # 回撤超过10%
            dd_factor = max(0.5, 1 - self.metrics.current_drawdown)
            base_ratio *= dd_factor
            logger.warning(f"回撤{self.metrics.current_drawdown:.1%}，仓位降至{dd_factor:.0%}")
        
        # 计算最终仓位
        position_value = balance * base_ratio
        
        # 限制最大最小值
        position_value = max(position_value, config.MIN_ORDER_USDT)
        position_value = min(position_value, config.MAX_ORDER_USDT)
        position_value = min(position_value, balance * 0.5)  # 最多使用50%资金
        
        # 转换为合约数量
        amount = position_value / current_price

        # Policy Layer 仓位调整（新增）
        if getattr(config, 'ENABLE_POLICY_LAYER', False):
            amount = self.get_policy_adjusted_position_size(amount)

        # 最小交易额保护（新增）
        min_amount = config.MIN_ORDER_USDT / current_price
        if amount < min_amount:
            original_amount = amount
            amount = min_amount
            logger.warning(f"⚠️ 调整后仓位 {original_amount:.6f} ({original_amount * current_price:.2f} USDT) "
                          f"低于最小交易额 {config.MIN_ORDER_USDT} USDT")
            logger.warning(f"   自动提高到最小交易额: {amount:.6f} ({amount * current_price:.2f} USDT)")

            # 检查是否超过账户余额的安全限制
            max_safe_value = balance * 0.8  # 最多使用80%资金
            if amount * current_price > max_safe_value:
                logger.error(f"❌ 最小交易额 {config.MIN_ORDER_USDT} USDT 超过账户余额的80% ({max_safe_value:.2f} USDT)")
                logger.error(f"   建议: 增加账户余额到至少 {config.MIN_ORDER_USDT / 0.1:.2f} USDT")
                return 0  # 返回0表示无法开仓

        logger.info(f"计算仓位: 余额={balance:.2f}, 比例={base_ratio:.2%}, "
                   f"价值={position_value:.2f}, 数量={amount:.6f}")

        return amount
    
    def _calculate_current_volatility(self, df: pd.DataFrame) -> float:
        """计算当前波动率"""
        try:
            volatility = calc_volatility(df['close'], period=config.VOLATILITY_LOOKBACK)
            return volatility.iloc[-1]
        except (IndexError, KeyError, ValueError) as e:
            logger.warning(f"波动率计算失败，使用默认值2%: {e}")
            return 0.02  # 默认2%
    
    def calculate_partial_position(
        self,
        total_amount: float,
        parts: int = 3,
        part_index: int = 0
    ) -> float:
        """
        计算分批建仓的单次数量
        采用金字塔式加仓（首次小，后续递增）
        """
        if parts <= 0:
            return total_amount
        
        # 金字塔权重: 1, 2, 3, ...
        weights = list(range(1, parts + 1))
        total_weight = sum(weights)
        
        if part_index < len(weights):
            ratio = weights[part_index] / total_weight
            return total_amount * ratio
        
        return 0
    
    # ==================== 止损止盈计算 ====================
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        side: str,
        df: pd.DataFrame = None
    ) -> float:
        """
        计算止损价格
        支持固定止损和 ATR 动态止损
        **现在会使用 Policy Layer 的参数**
        """
        # 检查是否启用 Policy Layer
        if getattr(config, 'ENABLE_POLICY_LAYER', False):
            return self.get_policy_adjusted_stop_loss(entry_price, side, df)

        # 混合止损策略：计算固定止损和ATR止损，取较宽的一个
        fixed_stop = self._calculate_fixed_stop_loss(entry_price, side)

        if config.USE_ATR_STOP_LOSS and df is not None:
            atr_stop = self._calculate_atr_stop_loss(entry_price, side, df)

            # 取较宽的止损（给交易更多空间）
            if side == 'long':
                # 做多：止损价格越低，止损空间越大
                final_stop = min(fixed_stop, atr_stop)
                stop_type = "固定" if final_stop == fixed_stop else "ATR"
            else:
                # 做空：止损价格越高，止损空间越大
                final_stop = max(fixed_stop, atr_stop)
                stop_type = "固定" if final_stop == fixed_stop else "ATR"

            logger.info(f"混合止损: 固定={fixed_stop:.2f}, ATR={atr_stop:.2f}, "
                       f"最终={final_stop:.2f} (使用{stop_type})")
            return final_stop
        else:
            return fixed_stop
    
    def _calculate_fixed_stop_loss(self, entry_price: float, side: str) -> float:
        """计算固定比例止损"""
        if side == 'long':
            return entry_price * (1 - config.STOP_LOSS_PERCENT / config.LEVERAGE)
        else:
            return entry_price * (1 + config.STOP_LOSS_PERCENT / config.LEVERAGE)
    
    def _calculate_atr_stop_loss(
        self,
        entry_price: float,
        side: str,
        df: pd.DataFrame
    ) -> float:
        """计算 ATR 动态止损"""
        try:
            atr = calc_atr(df['high'], df['low'], df['close'], period=14)
            current_atr = atr.iloc[-1]
            self.metrics.atr = current_atr
            self.metrics.atr_percent = current_atr / entry_price * 100
            
            atr_distance = current_atr * config.ATR_STOP_MULTIPLIER
            
            if side == 'long':
                stop_price = entry_price - atr_distance
            else:
                stop_price = entry_price + atr_distance
            
            # 确保不超过最大止损比例
            max_stop = self._calculate_fixed_stop_loss(entry_price, side)
            
            if side == 'long':
                stop_price = max(stop_price, max_stop)
            else:
                stop_price = min(stop_price, max_stop)
            
            logger.debug(f"ATR止损: ATR={current_atr:.2f}, 止损价={stop_price:.2f}")
            
            return stop_price
            
        except Exception as e:
            logger.error(f"计算ATR止损失败: {e}")
            return self._calculate_fixed_stop_loss(entry_price, side)
    
    def calculate_take_profit(
        self,
        entry_price: float,
        side: str,
        risk_reward_ratio: float = 2.0
    ) -> float:
        """
        计算止盈价格
        基于风险回报比
        **现在会使用 Policy Layer 的参数**
        """
        # 检查是否启用 Policy Layer
        if getattr(config, 'ENABLE_POLICY_LAYER', False):
            return self.get_policy_adjusted_take_profit(entry_price, side)

        # 原有逻辑保持不变
        stop_loss = self.calculate_stop_loss(entry_price, side)
        risk = abs(entry_price - stop_loss)
        reward = risk * risk_reward_ratio

        if side == 'long':
            take_profit = entry_price + reward
        else:
            take_profit = entry_price - reward

        # 也可以使用固定比例
        fixed_tp = entry_price * (1 + config.TAKE_PROFIT_PERCENT / config.LEVERAGE) if side == 'long' \
                   else entry_price * (1 - config.TAKE_PROFIT_PERCENT / config.LEVERAGE)

        # 取较大的止盈
        if side == 'long':
            take_profit = max(take_profit, fixed_tp)
        else:
            take_profit = min(take_profit, fixed_tp)

        return take_profit
    
    def calculate_trailing_stop(
        self,
        current_price: float,
        position: PositionInfo
    ) -> float:
        """计算移动止损价格"""
        if position.side == 'long':
            # 多仓：从最高价回撤
            trailing_price = position.highest_price * (1 - config.TRAILING_STOP_PERCENT)
            # 必须高于开仓价才启用
            if trailing_price > position.entry_price:
                return trailing_price
            return 0
        else:
            # 空仓：从最低价反弹
            trailing_price = position.lowest_price * (1 + config.TRAILING_STOP_PERCENT)
            # 必须低于开仓价才启用
            if trailing_price < position.entry_price:
                return trailing_price
            return 0

    def calculate_trailing_take_profit(
        self,
        current_price: float,
        position: PositionInfo
    ) -> float:
        """
        计算动态止盈价格（基于浮动盈利门槛和回撤均值）

        逻辑：
        1. 计算净盈利（扣除手续费）
        2. 检查是否超过最小盈利门槛
        3. 更新最大盈利
        4. 计算最近N次价格均值
        5. 判断是否跌破均值触发止盈

        Args:
            current_price: 当前价格
            position: 持仓信息

        Returns:
            止盈价格（0表示未触发）
        """
        # 1. 计算净盈利
        net_profit = position.calculate_net_profit(current_price)

        # 2. 检查是否超过最小盈利门槛
        if net_profit > config.MIN_PROFIT_THRESHOLD_USDT:
            position.profit_threshold_reached = True
            # 3. 更新最大盈利
            if net_profit > position.max_profit:
                position.max_profit = net_profit
                logger.info(f"[动态止盈] 更新最大盈利: {position.max_profit:.4f} USDT")

        # 4. 只有达到盈利门槛后才启用动态止盈
        if not position.profit_threshold_reached:
            return 0

        # 5. 更新最近N次价格
        position.update_recent_prices(current_price)

        # 6. 计算价格均值
        if len(position.recent_prices) < config.TRAILING_TP_PRICE_WINDOW:
            # 价格样本不足，不触发
            return 0

        price_avg = position.get_price_average()

        # 7. 判断是否跌破均值
        if position.side == 'long':
            # 多仓：当前价格跌破均值
            fallback_threshold = price_avg * (1 - config.TRAILING_TP_FALLBACK_PERCENT)
            if current_price <= fallback_threshold:
                logger.info(
                    f"[动态止盈] 多仓触发: 当前价 {current_price:.2f} "
                    f"<= 回撤阈值 {fallback_threshold:.2f} (均值 {price_avg:.2f})"
                )
                return current_price
        else:
            # 空仓：当前价格突破均值
            fallback_threshold = price_avg * (1 + config.TRAILING_TP_FALLBACK_PERCENT)
            if current_price >= fallback_threshold:
                logger.info(
                    f"[动态止盈] 空仓触发: 当前价 {current_price:.2f} "
                    f">= 回撤阈值 {fallback_threshold:.2f} (均值 {price_avg:.2f})"
                )
                return current_price

        return 0

    # ==================== 止损检查 ====================
    
    def check_stop_loss(
        self,
        current_price: float,
        position: PositionInfo,
        df: pd.DataFrame = None
    ) -> StopLossResult:
        """
        检查是否触发止损/止盈
        返回止损结果
        """
        result = StopLossResult(current_price=current_price)

        # 更新持仓价格信息
        position.update_price(current_price)

        # ===== 调试日志：打印关键变量 =====
        logger.info("=" * 60)
        logger.info(f"[止损检查] 当前价: {current_price:.2f}")
        logger.info(f"[止损检查] 开仓价: {position.entry_price:.2f}")
        logger.info(f"[止损检查] 持仓方向: {position.side}")
        logger.info(f"[止损检查] 持仓数量: {position.amount:.8f}")
        logger.info(f"[止损检查] 最高价: {position.highest_price:.2f}")
        logger.info(f"[止损检查] 最低价: {position.lowest_price:.2f}")
        logger.info(f"[止损检查] ATR止损价: {position.stop_loss_price:.2f}")
        logger.info(f"[止损检查] 固定止盈价: {position.take_profit_price:.2f}")
        
        # 计算当前盈亏比例
        if position.side == 'long':
            pnl_pct = (current_price - position.entry_price) / position.entry_price * config.LEVERAGE * 100
        else:
            pnl_pct = (position.entry_price - current_price) / position.entry_price * config.LEVERAGE * 100
        
        result.pnl_percent = pnl_pct
        
        # 1. 检查固定止损
        stop_loss_pct = -config.STOP_LOSS_PERCENT * 100
        if pnl_pct <= stop_loss_pct:
            result.should_stop = True
            result.stop_type = "stop_loss"
            result.reason = f"触发止损: 亏损 {pnl_pct:.2f}%"
            result.stop_price = position.stop_loss_price
            return result
        
        # 2. 检查 ATR 止损
        if config.USE_ATR_STOP_LOSS and df is not None and position.stop_loss_price > 0:
            if position.side == 'long' and current_price <= position.stop_loss_price:
                result.should_stop = True
                result.stop_type = "atr_stop"
                result.reason = f"触发ATR止损: 价格 {current_price:.2f} <= {position.stop_loss_price:.2f}"
                result.stop_price = position.stop_loss_price
                return result
            
            if position.side == 'short' and current_price >= position.stop_loss_price:
                result.should_stop = True
                result.stop_type = "atr_stop"
                result.reason = f"触发ATR止损: 价格 {current_price:.2f} >= {position.stop_loss_price:.2f}"
                result.stop_price = position.stop_loss_price
                return result
        
        # 3. 检查固定止盈
        take_profit_pct = config.TAKE_PROFIT_PERCENT * 100
        if pnl_pct >= take_profit_pct:
            result.should_stop = True
            result.stop_type = "take_profit"
            result.reason = f"触发固定止盈: 盈利 {pnl_pct:.2f}%"
            result.stop_price = position.take_profit_price
            return result

        # 3.5. 检查动态止盈（基于浮动盈利门槛和回撤均值）
        if config.ENABLE_TRAILING_TAKE_PROFIT:
            trailing_tp = self.calculate_trailing_take_profit(current_price, position)

            # ===== 调试日志：动态止盈详情 =====
            net_profit = position.calculate_net_profit(current_price)
            logger.info(f"[动态止盈] 净盈利: {net_profit:.4f} USDT")
            logger.info(f"[动态止盈] 最大盈利: {position.max_profit:.4f} USDT")
            logger.info(f"[动态止盈] 盈利门槛: {config.MIN_PROFIT_THRESHOLD_USDT:.4f} USDT")
            logger.info(f"[动态止盈] 门槛已达: {position.profit_threshold_reached}")
            logger.info(f"[动态止盈] 价格窗口: {position.recent_prices}")
            if len(position.recent_prices) >= config.TRAILING_TP_PRICE_WINDOW:
                logger.info(f"[动态止盈] 价格均值: {position.get_price_average():.2f}")
            logger.info(f"[动态止盈] 计算结果: {trailing_tp:.2f}")

            if trailing_tp > 0:
                position.trailing_take_profit_price = trailing_tp

                # 计算净盈利百分比
                net_profit_pct = (net_profit / (position.entry_price * position.amount)) * 100

                result.should_stop = True
                result.stop_type = "trailing_take_profit"
                result.reason = (
                    f"触发动态止盈: 价格跌破{config.TRAILING_TP_PRICE_WINDOW}次均值 "
                    f"(均值: {position.get_price_average():.2f}, "
                    f"最大盈利: {position.max_profit:.4f} USDT)"
                )
                result.stop_price = trailing_tp
                result.pnl_percent = net_profit_pct

                logger.warning(
                    f"!!! 触发动态止盈 !!! "
                    f"净盈利 {net_profit:.4f} USDT ({net_profit_pct:.2f}%)"
                )
                return result

        # 4. 检查移动止损
        trailing_stop = self.calculate_trailing_stop(current_price, position)

        # ===== 调试日志：移动止损详情 =====
        logger.info(f"[移动止损] 计算结果: {trailing_stop:.2f}")
        logger.info(f"[移动止损] TRAILING_STOP_PERCENT: {config.TRAILING_STOP_PERCENT}")
        if position.side == 'long':
            expected_trailing = position.highest_price * (1 - config.TRAILING_STOP_PERCENT)
            logger.info(f"[移动止损] 预期值(多仓): {position.highest_price:.2f} × {1-config.TRAILING_STOP_PERCENT} = {expected_trailing:.2f}")
            logger.info(f"[移动止损] 是否高于开仓价: {expected_trailing:.2f} > {position.entry_price:.2f} = {expected_trailing > position.entry_price}")
            logger.info(f"[移动止损] 当前价是否触发: {current_price:.2f} <= {trailing_stop:.2f} = {current_price <= trailing_stop if trailing_stop > 0 else False}")
        else:
            expected_trailing = position.lowest_price * (1 + config.TRAILING_STOP_PERCENT)
            logger.info(f"[移动止损] 预期值(空仓): {position.lowest_price:.2f} × {1+config.TRAILING_STOP_PERCENT} = {expected_trailing:.2f}")
            logger.info(f"[移动止损] 是否低于开仓价: {expected_trailing:.2f} < {position.entry_price:.2f} = {expected_trailing < position.entry_price}")
            logger.info(f"[移动止损] 当前价是否触发: {current_price:.2f} >= {trailing_stop:.2f} = {current_price >= trailing_stop if trailing_stop > 0 else False}")
        logger.info("=" * 60)

        if trailing_stop > 0:
            position.trailing_stop_price = trailing_stop

            if position.side == 'long' and current_price <= trailing_stop:
                result.should_stop = True
                result.stop_type = "trailing_stop"
                result.reason = f"触发移动止损: 从最高点 {position.highest_price:.2f} 回撤"
                result.stop_price = trailing_stop
                logger.warning(f"!!! 触发移动止损 !!! 当前价 {current_price:.2f} <= 止损价 {trailing_stop:.2f}")
                return result

            if position.side == 'short' and current_price >= trailing_stop:
                result.should_stop = True
                result.stop_type = "trailing_stop"
                result.reason = f"触发移动止损: 从最低点 {position.lowest_price:.2f} 反弹"
                result.stop_price = trailing_stop
                logger.warning(f"!!! 触发移动止损 !!! 当前价 {current_price:.2f} >= 止损价 {trailing_stop:.2f}")
                return result
        else:
            logger.info(f"[移动止损] 未启用 (trailing_stop = {trailing_stop})")

        # 保存更新后的持仓状态到数据库（包括更新的highest_price和lowest_price）
        self._save_position_to_db()

        return result
    
    # ==================== 开仓控制 ====================
    
    def set_position(
        self,
        side: str,
        amount: float,
        entry_price: float,
        df: pd.DataFrame = None,
        highest_price: float = None,
        lowest_price: float = None,
        entry_time: datetime = None
    ):
        """设置新持仓"""
        # 如果没有提供历史价格，使用开仓价作为默认值
        if highest_price is None:
            highest_price = entry_price
        if lowest_price is None:
            lowest_price = entry_price
        if entry_time is None:
            entry_time = datetime.now()

        self.position = PositionInfo(
            side=side,
            amount=amount,
            entry_price=entry_price,
            entry_time=entry_time,
            current_price=entry_price,
            highest_price=highest_price,
            lowest_price=lowest_price,
        )

        # 计算止损止盈价格
        self.position.stop_loss_price = self.calculate_stop_loss(entry_price, side, df)
        self.position.take_profit_price = self.calculate_take_profit(entry_price, side)

        # ===== 初始化开仓手续费（动态止盈功能） =====
        self.position.entry_fee = self.position.calculate_entry_fee(entry_price, amount)
        logger.info(f"[持仓] 开仓手续费: {self.position.entry_fee:.4f} USDT")

        self.last_trade_time = datetime.now()
        self.daily_trades += 1

        # 保存持仓状态到数据库
        self._save_position_to_db()

        logger.info(f"新建持仓: {side} {amount:.6f} @ {entry_price:.2f}")
        logger.info(f"止损: {self.position.stop_loss_price:.2f}, "
                   f"止盈: {self.position.take_profit_price:.2f}")
    
    def add_position(
        self,
        additional_amount: float,
        price: float
    ):
        """加仓"""
        if not self.position:
            return
        
        # 计算新的平均开仓价
        old_value = self.position.amount * self.position.entry_price
        new_value = additional_amount * price
        total_amount = self.position.amount + additional_amount
        
        new_entry_price = (old_value + new_value) / total_amount
        
        self.position.amount = total_amount
        self.position.entry_price = new_entry_price
        self.position.add_count += 1
        
        # 重新计算止损止盈
        self.position.stop_loss_price = self.calculate_stop_loss(new_entry_price, self.position.side)
        self.position.take_profit_price = self.calculate_take_profit(new_entry_price, self.position.side)
        
        logger.info(f"加仓: +{additional_amount:.6f} @ {price:.2f}")
        logger.info(f"新均价: {new_entry_price:.2f}, 总量: {total_amount:.6f}")
    
    def partial_close(
        self,
        close_ratio: float,
        price: float,
        pnl: float
    ):
        """部分平仓"""
        if not self.position:
            return
        
        close_amount = self.position.amount * close_ratio
        self.position.amount -= close_amount
        self.position.partial_close_count += 1
        
        # 更新统计
        self.record_trade_result(pnl)
        
        logger.info(f"部分平仓: {close_ratio:.0%} ({close_amount:.6f}) @ {price:.2f}")
        logger.info(f"剩余持仓: {self.position.amount:.6f}")
        
        # 如果全部平完
        if self.position.amount <= 0:
            self.clear_position()
    
    def clear_position(self):
        """清除持仓"""
        self.position = None
        logger.info("持仓已清除")

    def has_position(self) -> bool:
        """
        检查是否有持仓

        Returns:
            bool: True表示有持仓，False表示无持仓
        """
        return self.position is not None

    def open_position(self, side: str, amount: float, entry_price: float, df: pd.DataFrame = None):
        """开仓（向后兼容别名）"""
        return self.set_position(side, amount, entry_price, df)

    def close_position(self, exit_price: float = None):
        """平仓（向后兼容别名）"""
        if self.position and exit_price:
            # 更新最终价格以计算盈亏
            self.position.update_price(exit_price)
        self.clear_position()

    # ==================== 交易控制 ====================
    
    def can_open_position(self) -> Tuple[bool, str]:
        """检查是否可以开仓"""
        # 1. 检查是否有持仓
        if self.position is not None:
            return False, "已有持仓"
        
        # 2. 检查冷却时间
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < self.trade_cooldown:
                remaining = self.trade_cooldown - elapsed
                return False, f"交易冷却中，剩余 {remaining:.0f} 秒"
        
        # 3. 检查亏损后冷却
        if self.last_loss_time:
            elapsed = (datetime.now() - self.last_loss_time).total_seconds()
            if elapsed < self.loss_cooldown:
                remaining = self.loss_cooldown - elapsed
                return False, f"亏损冷却中，剩余 {remaining:.0f} 秒"
        
        # 4. 检查日内交易次数
        if self.daily_trades >= 20:
            return False, "已达日内交易次数上限"
        
        # 5. 检查日内亏损
        if self.daily_loss < -500:  # 日亏损超过 500 USDT
            return False, f"日内亏损过大: {self.daily_loss:.2f}"
        
        # 6. 检查连续亏损
        if self.metrics.consecutive_losses >= 5:
            return False, f"连续亏损 {self.metrics.consecutive_losses} 次，暂停交易"
        
        # 7. 检查回撤
        if self.metrics.current_drawdown > 0.2:  # 回撤超过 20%
            return False, f"回撤过大: {self.metrics.current_drawdown:.1%}"
        
        return True, ""
    
    def can_add_position(self, current_price: float) -> Tuple[bool, str]:
        """检查是否可以加仓"""
        if not self.position:
            return False, "无持仓"
        
        # 限制加仓次数
        if self.position.add_count >= 2:
            return False, "已达加仓次数上限"
        
        # 检查盈亏状态（只有盈利时才加仓）
        if self.position.side == 'long':
            if current_price <= self.position.entry_price:
                return False, "多仓亏损中，不宜加仓"
        else:
            if current_price >= self.position.entry_price:
                return False, "空仓亏损中，不宜加仓"
        
        # 检查加仓间隔
        min_profit_pct = 0.5  # 至少盈利 0.5% 才加仓
        if abs(self.position.unrealized_pnl_pct) < min_profit_pct:
            return False, f"盈利不足 {min_profit_pct}%"
        
        return True, ""
    
    # ==================== 统计和记录 ====================
    
    def record_trade_result(self, pnl: float):
        """记录交易结果"""
        self.daily_pnl += pnl
        self.metrics.total_pnl += pnl

        # 只计算有明确结果的交易（排除 pnl=0 的情况）
        if pnl > 0:
            self.metrics.total_trades += 1
            self.metrics.winning_trades += 1
            self.metrics.consecutive_wins += 1
            self.metrics.consecutive_losses = 0
            self.metrics.max_consecutive_wins = max(
                self.metrics.max_consecutive_wins,
                self.metrics.consecutive_wins
            )
        elif pnl < 0:
            self.metrics.total_trades += 1
            self.metrics.losing_trades += 1
            self.metrics.consecutive_losses += 1
            self.metrics.consecutive_wins = 0
            self.metrics.max_consecutive_losses = max(
                self.metrics.max_consecutive_losses,
                self.metrics.consecutive_losses
            )
            self.daily_loss += pnl
            self.last_loss_time = datetime.now()
        
        # 更新胜率
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = self.metrics.winning_trades / self.metrics.total_trades
        
        # 更新平均盈亏
        wins = [t['pnl'] for t in self.trade_history if t.get('pnl', 0) > 0]
        losses = [t['pnl'] for t in self.trade_history if t.get('pnl', 0) < 0]
        
        if wins:
            self.metrics.avg_win = sum(wins) / len(wins)
        if losses:
            self.metrics.avg_loss = sum(losses) / len(losses)
        
        # 更新盈亏比
        if losses and sum(losses) != 0:
            self.metrics.profit_factor = abs(sum(wins) / sum(losses)) if wins else 0
        
        # 更新期望值
        self.metrics.expectancy = (
            self.metrics.win_rate * self.metrics.avg_win +
            (1 - self.metrics.win_rate) * self.metrics.avg_loss
        )
        
        # 重新计算 Kelly
        self.metrics.calculate_kelly()
        
        # 记录到历史
        self.trade_history.append({
            'time': datetime.now().isoformat(),
            'pnl': pnl,
        })
        
        logger.info(f"交易记录: PnL={pnl:.2f}, 胜率={self.metrics.win_rate:.1%}, "
                   f"连胜={self.metrics.consecutive_wins}, 连亏={self.metrics.consecutive_losses}")
    
    def update_equity(self, equity: float):
        """更新权益曲线"""
        if self.metrics.peak_equity == 0:
            self.metrics.peak_equity = equity
        else:
            self.metrics.peak_equity = max(self.metrics.peak_equity, equity)
        
        # 计算回撤
        if self.metrics.peak_equity > 0:
            self.metrics.current_drawdown = (
                self.metrics.peak_equity - equity
            ) / self.metrics.peak_equity
            self.metrics.max_drawdown = max(
                self.metrics.max_drawdown,
                self.metrics.current_drawdown
            )
        
        # 保存权益曲线
        if config.SAVE_EQUITY_CURVE:
            self.equity_curve.append({
                'time': datetime.now().isoformat(),
                'equity': equity,
                'drawdown': self.metrics.current_drawdown,
            })
    
    def reset_daily_stats(self):
        """重置日内统计（每日调用）"""
        logger.info(f"重置日内统计 - 昨日: 交易={self.daily_trades}次, "
                   f"盈亏={self.daily_pnl:.2f}, 亏损={self.daily_loss:.2f}")
        
        self.daily_loss = 0
        self.daily_trades = 0
        self.daily_pnl = 0
    
    def _save_position_to_db(self):
        """保存持仓状态到数据库"""
        if not self.position:
            return

        try:
            db.log_position_snapshot(
                symbol=config.SYMBOL,
                side=self.position.side,
                amount=self.position.amount,
                entry_price=self.position.entry_price,
                current_price=self.position.current_price,
                unrealized_pnl=self.position.unrealized_pnl,
                leverage=config.LEVERAGE,
                highest_price=self.position.highest_price,
                lowest_price=self.position.lowest_price,
                entry_time=self.position.entry_time.isoformat() if self.position.entry_time else None
            )
            logger.debug(f"💾 持仓状态已保存: highest={self.position.highest_price:.2f}, "
                        f"lowest={self.position.lowest_price:.2f}, "
                        f"current={self.position.current_price:.2f}")
        except Exception as e:
            logger.error(f"❌ 保存持仓状态失败: {e}")

    def get_risk_report(self) -> Dict:
        """获取风险报告"""
        return {
            'metrics': {
                'total_trades': self.metrics.total_trades,
                'win_rate': f"{self.metrics.win_rate:.1%}",
                'profit_factor': f"{self.metrics.profit_factor:.2f}",
                'expectancy': f"{self.metrics.expectancy:.2f}",
                'max_drawdown': f"{self.metrics.max_drawdown:.1%}",
                'current_drawdown': f"{self.metrics.current_drawdown:.1%}",
                'kelly_fraction': f"{self.metrics.kelly_fraction:.2%}",
                'consecutive_losses': self.metrics.consecutive_losses,
                'max_consecutive_losses': self.metrics.max_consecutive_losses,
            },
            'daily': {
                'trades': self.daily_trades,
                'pnl': f"{self.daily_pnl:.2f}",
                'loss': f"{self.daily_loss:.2f}",
            },
            'position': {
                'side': self.position.side if self.position else None,
                'amount': self.position.amount if self.position else 0,
                'entry_price': self.position.entry_price if self.position else 0,
                'unrealized_pnl': self.position.unrealized_pnl if self.position else 0,
                'unrealized_pnl_pct': f"{self.position.unrealized_pnl_pct:.2f}%" if self.position else "0%",
            } if self.position else None,
        }


# ==================== 分批建仓管理器（新增）====================

class PositionBuilder:
    """分批建仓管理器"""
    
    def __init__(
        self,
        total_amount: float,
        parts: int = 3,
        entry_type: str = "pyramid"  # pyramid / equal / reverse_pyramid
    ):
        self.total_amount = total_amount
        self.parts = parts
        self.entry_type = entry_type
        self.current_part = 0
        self.entries: List[Dict] = []
    
    def get_next_amount(self) -> Optional[float]:
        """获取下一次建仓数量"""
        if self.current_part >= self.parts:
            return None
        
        if self.entry_type == "pyramid":
            # 金字塔：首次最小，逐渐增大
            weights = list(range(1, self.parts + 1))
        elif self.entry_type == "reverse_pyramid":
            # 倒金字塔：首次最大，逐渐减小
            weights = list(range(self.parts, 0, -1))
        else:  # equal
            # 等分
            weights = [1] * self.parts
        
        total_weight = sum(weights)
        amount = self.total_amount * weights[self.current_part] / total_weight
        
        return amount
    
    def record_entry(self, amount: float, price: float):
        """记录建仓"""
        self.entries.append({
            'part': self.current_part,
            'amount': amount,
            'price': price,
            'time': datetime.now().isoformat(),
        })
        self.current_part += 1
    
    def get_average_price(self) -> float:
        """获取平均成本"""
        if not self.entries:
            return 0
        
        total_value = sum(e['amount'] * e['price'] for e in self.entries)
        total_amount = sum(e['amount'] for e in self.entries)
        
        return total_value / total_amount if total_amount > 0 else 0
    
    def get_total_amount(self) -> float:
        """获取已建仓总量"""
        return sum(e['amount'] for e in self.entries)
    
    def is_complete(self) -> bool:
        """是否建仓完成"""
        return self.current_part >= self.parts
    
    def reset(self):
        """重置"""
        self.current_part = 0
        self.entries = []


# ==================== 分批平仓管理器（新增）====================

class PositionCloser:
    """分批平仓管理器"""
    
    def __init__(
        self,
        total_amount: float,
        targets: List[Dict] = None  # [{'price': 100, 'ratio': 0.3}, ...]
    ):
        self.total_amount = total_amount
        self.remaining_amount = total_amount
        self.targets = targets or []
        self.exits: List[Dict] = []
    
    def add_target(self, price: float, ratio: float):
        """添加止盈目标"""
        self.targets.append({
            'price': price,
            'ratio': ratio,
            'triggered': False,
        })
    
    def check_targets(self, current_price: float, position_side: str) -> Optional[float]:
        """
        检查是否触发平仓目标
        返回需要平仓的数量
        """
        for target in self.targets:
            if target['triggered']:
                continue
            
            triggered = False
            if position_side == 'long' and current_price >= target['price']:
                triggered = True
            elif position_side == 'short' and current_price <= target['price']:
                triggered = True
            
            if triggered:
                target['triggered'] = True
                close_amount = self.total_amount * target['ratio']
                close_amount = min(close_amount, self.remaining_amount)
                return close_amount
        
        return None
    
    def record_exit(self, amount: float, price: float, pnl: float):
        """记录平仓"""
        self.remaining_amount -= amount
        self.exits.append({
            'amount': amount,
            'price': price,
            'pnl': pnl,
            'time': datetime.now().isoformat(),
        })
    
    def get_total_pnl(self) -> float:
        """获取总盈亏"""
        return sum(e['pnl'] for e in self.exits)
    
    def is_complete(self) -> bool:
        """是否全部平仓完成"""
        return self.remaining_amount <= 0


# ==================== 回撤控制器（新增 - 来自 Qbot）====================

class DrawdownController:
    """回撤控制器"""
    
    def __init__(
        self,
        max_daily_drawdown: float = 0.05,    # 日最大回撤 5%
        max_total_drawdown: float = 0.15,    # 总最大回撤 15%
        recovery_threshold: float = 0.5      # 恢复阈值
    ):
        self.max_daily_drawdown = max_daily_drawdown
        self.max_total_drawdown = max_total_drawdown
        self.recovery_threshold = recovery_threshold
        
        self.daily_peak = 0
        self.total_peak = 0
        self.is_locked = False
        self.lock_reason = ""
        self.lock_time: Optional[datetime] = None
    
    def update(self, equity: float) -> Tuple[bool, str]:
        """
        更新权益并检查是否需要锁定
        返回: (是否锁定, 原因)
        """
        # 更新峰值
        if self.daily_peak == 0:
            self.daily_peak = equity
        if self.total_peak == 0:
            self.total_peak = equity
        
        self.daily_peak = max(self.daily_peak, equity)
        self.total_peak = max(self.total_peak, equity)
        
        # 计算回撤
        daily_dd = (self.daily_peak - equity) / self.daily_peak if self.daily_peak > 0 else 0
        total_dd = (self.total_peak - equity) / self.total_peak if self.total_peak > 0 else 0
        
        # 检查是否触发锁定
        if daily_dd >= self.max_daily_drawdown:
            self.is_locked = True
            self.lock_reason = f"日回撤 {daily_dd:.1%} 超过限制 {self.max_daily_drawdown:.1%}"
            self.lock_time = datetime.now()
            return True, self.lock_reason
        
        if total_dd >= self.max_total_drawdown:
            self.is_locked = True
            self.lock_reason = f"总回撤 {total_dd:.1%} 超过限制 {self.max_total_drawdown:.1%}"
            self.lock_time = datetime.now()
            return True, self.lock_reason
        
        # 检查是否可以解锁（恢复了一定比例）
        if self.is_locked and self.lock_time:
            recovery = (equity - (self.total_peak * (1 - self.max_total_drawdown))) / \
                      (self.total_peak * self.max_total_drawdown)
            
            if recovery >= self.recovery_threshold:
                # 恢复超过阈值，解锁
                hours_passed = (datetime.now() - self.lock_time).total_seconds() / 3600
                if hours_passed >= 4:  # 至少锁定4小时
                    self.is_locked = False
                    self.lock_reason = ""
                    return False, "回撤恢复，解除锁定"
        
        return self.is_locked, self.lock_reason
    
    def reset_daily(self):
        """重置日内统计"""
        self.daily_peak = 0

    def can_trade(self) -> Tuple[bool, str]:
        """是否可以交易"""
        if self.is_locked:
            return False, self.lock_reason
        return True, ""


# 向后兼容别名
Position = PositionInfo
