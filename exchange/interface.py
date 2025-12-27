"""
交易所统一接口定义
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from dataclasses import dataclass
import pandas as pd


@dataclass
class TickerData:
    """行情数据"""
    symbol: str
    last: float
    bid: Optional[float]
    ask: Optional[float]
    volume: Optional[float]
    timestamp: int
    raw_data: Dict


@dataclass
class PositionData:
    """持仓数据"""
    side: str  # 'long' or 'short'
    amount: float
    entry_price: float
    unrealized_pnl: float
    leverage: int
    margin_mode: str
    raw_data: Dict


@dataclass
class OrderResult:
    """订单结果"""
    success: bool
    order_id: Optional[str] = None
    price: Optional[float] = None
    amount: Optional[float] = None
    side: Optional[str] = None
    error: Optional[str] = None
    raw_data: Optional[Dict] = None


class ExchangeInterface(ABC):
    """交易所统一接口"""

    def __init__(self, config: Dict):
        self.config = config
        self.exchange = None

    # ========== 生命周期管理 ==========

    @abstractmethod
    def connect(self) -> bool:
        """连接交易所"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    # ========== 市场数据接口 ==========

    @abstractmethod
    def get_ticker(self, symbol: str = None) -> Optional[TickerData]:
        """获取行情"""
        pass

    @abstractmethod
    def get_klines(self, symbol: str = None, timeframe: str = None,
                   limit: int = None) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        pass

    @abstractmethod
    def get_orderbook(self, symbol: str = None, limit: int = 20) -> Optional[Dict]:
        """获取订单簿"""
        pass

    # ========== 账户接口 ==========

    @abstractmethod
    def get_balance(self) -> float:
        """获取账户余额（USDT）"""
        pass

    @abstractmethod
    def get_positions(self, symbol: str = None) -> List[PositionData]:
        """获取持仓列表"""
        pass

    # ========== 交易接口 ==========

    @abstractmethod
    def open_long(self, amount: float, df: pd.DataFrame = None, **kwargs) -> OrderResult:
        """开多单"""
        pass

    @abstractmethod
    def open_short(self, amount: float, df: pd.DataFrame = None, **kwargs) -> OrderResult:
        """开空单"""
        pass

    @abstractmethod
    def close_position(self, reason: str = "", position_data: Dict = None) -> bool:
        """平仓"""
        pass

    @abstractmethod
    def close_all_positions(self) -> List[OrderResult]:
        """一键平仓所有持仓"""
        pass

    # ========== 交易参数设置 ==========

    @abstractmethod
    def set_leverage(self, leverage: int, symbol: str = None) -> bool:
        """设置杠杆"""
        pass

    @abstractmethod
    def set_margin_mode(self, mode: str, symbol: str = None) -> bool:
        """设置保证金模式"""
        pass

    # ========== 辅助方法（可选实现）==========

    def fetch_multi_timeframe_data(self, timeframes: List[str]) -> Dict[str, pd.DataFrame]:
        """获取多时间周期数据（默认实现）"""
        result = {}
        for tf in timeframes:
            df = self.get_klines(timeframe=tf)
            if df is not None:
                result[tf] = df
        return result

    def get_exchange_name(self) -> str:
        """获取交易所名称"""
        return getattr(self, 'exchange_name', 'unknown')
