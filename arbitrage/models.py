"""
套利引擎数据模型
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from exchange.interface import OrderResult


@dataclass
class SpreadData:
    """价差数据"""
    exchange_a: str  # 买入交易所
    exchange_b: str  # 卖出交易所
    symbol: str  # 交易对
    buy_price: float  # 买入价格 (exchange_a的ask)
    sell_price: float  # 卖出价格 (exchange_b的bid)
    spread_pct: float  # 价差百分比
    timestamp: int  # 时间戳(毫秒)

    def __str__(self) -> str:
        return (f"Spread({self.exchange_a}->{self.exchange_b}: "
                f"{self.spread_pct:.3f}%, buy={self.buy_price:.2f}, sell={self.sell_price:.2f})")


@dataclass
class ArbitrageOpportunity:
    """套利机会"""
    buy_exchange: str  # 买入交易所
    sell_exchange: str  # 卖出交易所
    symbol: str  # 交易对
    buy_price: float  # 买入价格
    sell_price: float  # 卖出价格
    spread_pct: float  # 价差百分比
    gross_profit: float  # 毛利润(每单位)
    net_profit: float  # 净利润(每单位)
    buy_exchange_fee: float  # 买入手续费率
    sell_exchange_fee: float  # 卖出手续费率
    estimated_buy_slippage: float  # 估算买入滑点
    estimated_sell_slippage: float  # 估算卖出滑点
    timestamp: int  # 时间戳(毫秒)

    # 订单簿深度信息
    buy_orderbook_depth: Optional[float] = None  # 买入订单簿深度(USDT)
    sell_orderbook_depth: Optional[float] = None  # 卖出订单簿深度(USDT)

    # 风险评分
    risk_score: Optional[float] = None  # 风险评分(0-1, 越低越好)

    def __str__(self) -> str:
        return (f"Opportunity({self.buy_exchange}->{self.sell_exchange}: "
                f"spread={self.spread_pct:.3f}%, net_profit={self.net_profit:.4f})")


@dataclass
class ArbitrageTrade:
    """套利交易记录"""
    opportunity: ArbitrageOpportunity  # 套利机会
    status: str  # 状态: PENDING, EXECUTING_BUY, EXECUTING_SELL, ROLLING_BACK, COMPLETED, FAILED
    amount: float  # 交易数量(USDT)

    # 订单结果
    buy_order: Optional[OrderResult] = None  # 买入订单结果
    sell_order: Optional[OrderResult] = None  # 卖出订单结果

    # 盈亏信息
    actual_pnl: Optional[float] = None  # 实际盈亏
    expected_pnl: Optional[float] = None  # 预期盈亏

    # 失败信息
    failure_reason: Optional[str] = None  # 失败原因

    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    buy_executed_at: Optional[datetime] = None  # 买入执行时间
    sell_executed_at: Optional[datetime] = None  # 卖出执行时间
    completed_at: Optional[datetime] = None  # 完成时间

    # 执行统计
    buy_execution_time: Optional[float] = None  # 买入执行耗时(秒)
    sell_execution_time: Optional[float] = None  # 卖出执行耗时(秒)
    total_execution_time: Optional[float] = None  # 总执行耗时(秒)

    def __str__(self) -> str:
        return (f"Trade({self.opportunity.buy_exchange}->{self.opportunity.sell_exchange}: "
                f"status={self.status}, amount={self.amount:.2f}, pnl={self.actual_pnl})")

    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == "COMPLETED"

    def is_failed(self) -> bool:
        """是否失败"""
        return self.status == "FAILED"

    def is_executing(self) -> bool:
        """是否正在执行"""
        return self.status in ["EXECUTING_BUY", "EXECUTING_SELL", "ROLLING_BACK"]

    def calculate_execution_time(self):
        """计算执行时间"""
        if self.buy_executed_at and self.created_at:
            self.buy_execution_time = (self.buy_executed_at - self.created_at).total_seconds()

        if self.sell_executed_at and self.buy_executed_at:
            self.sell_execution_time = (self.sell_executed_at - self.buy_executed_at).total_seconds()

        if self.completed_at and self.created_at:
            self.total_execution_time = (self.completed_at - self.created_at).total_seconds()


# 状态常量
class TradeStatus:
    """交易状态常量"""
    PENDING = "PENDING"  # 待执行
    EXECUTING_BUY = "EXECUTING_BUY"  # 执行买腿
    EXECUTING_SELL = "EXECUTING_SELL"  # 执行卖腿
    ROLLING_BACK = "ROLLING_BACK"  # 回滚中
    COMPLETED = "COMPLETED"  # 已完成
    FAILED = "FAILED"  # 失败
