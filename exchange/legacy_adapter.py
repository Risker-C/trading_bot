"""
向后兼容适配器 - 将 ExchangeInterface 适配为 bot.py 期望的格式
解决类型不匹配问题：dataclass → dict/boolean
"""
from typing import Optional, List, Dict
import pandas as pd
from .interface import ExchangeInterface, TickerData, PositionData, OrderResult


class LegacyAdapter:
    """
    适配器类：将新的 ExchangeInterface 适配为旧的 bot.py 期望格式

    转换规则：
    - PositionData (dataclass) → dict
    - OrderResult (dataclass) → boolean (向后兼容)
    - TickerData 保持不变（bot.py 已适配）
    """

    def __init__(self, exchange: ExchangeInterface):
        """
        初始化适配器

        Args:
            exchange: ExchangeInterface 实例
        """
        self._exchange = exchange
        self.risk_manager = None  # 兼容 bot.py:57

    # ========== 生命周期管理 ==========

    def connect(self) -> bool:
        """连接交易所"""
        return self._exchange.connect()

    def disconnect(self):
        """断开连接"""
        return self._exchange.disconnect()

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._exchange.is_connected()

    # ========== 市场数据接口 ==========

    def get_ticker(self, symbol: str = None) -> Optional[TickerData]:
        """获取行情（保持 TickerData 格式）"""
        return self._exchange.get_ticker(symbol)

    def get_klines(self, symbol: str = None, timeframe: str = None,
                   limit: int = None) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        return self._exchange.get_klines(symbol, timeframe, limit)

    def get_orderbook(self, symbol: str = None, limit: int = 20) -> Optional[Dict]:
        """获取订单簿"""
        return self._exchange.get_orderbook(symbol, limit)

    # ========== 账户接口 ==========

    def get_balance(self) -> float:
        """获取账户余额（USDT）"""
        return self._exchange.get_balance()

    def get_positions(self, symbol: str = None) -> List[Dict]:
        """
        获取持仓列表（转换为字典格式）

        转换：List[PositionData] → List[Dict]
        """
        positions = self._exchange.get_positions(symbol)

        # 转换 dataclass 为 dict
        return [
            {
                'side': pos.side,
                'amount': pos.amount,
                'entry_price': pos.entry_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'leverage': pos.leverage,
                'margin_mode': pos.margin_mode,
                'raw_data': pos.raw_data
            }
            for pos in positions
        ]

    # ========== 交易接口 ==========

    def open_long(self, amount: float, df: pd.DataFrame = None, **kwargs) -> bool:
        """
        开多单（返回 boolean）

        转换：OrderResult → boolean
        """
        result = self._exchange.open_long(amount, df, **kwargs)

        # 保存最后的订单结果供后续使用
        self._last_order_result = result

        # 返回 boolean（向后兼容）
        return result.success

    def open_short(self, amount: float, df: pd.DataFrame = None, **kwargs) -> bool:
        """
        开空单（返回 boolean）

        转换：OrderResult → boolean
        """
        result = self._exchange.open_short(amount, df, **kwargs)

        # 保存最后的订单结果
        self._last_order_result = result

        # 返回 boolean
        return result.success

    def close_position(self, reason: str = "", position_data: Dict = None) -> bool:
        """平仓"""
        return self._exchange.close_position(reason, position_data)

    def close_all_positions(self) -> List[OrderResult]:
        """一键平仓所有持仓"""
        return self._exchange.close_all_positions()

    # ========== 交易参数设置 ==========

    def set_leverage(self, leverage: int, symbol: str = None) -> bool:
        """设置杠杆"""
        return self._exchange.set_leverage(leverage, symbol)

    def set_margin_mode(self, mode: str, symbol: str = None) -> bool:
        """设置保证金模式"""
        return self._exchange.set_margin_mode(mode, symbol)

    def place_order(self, symbol: str, side: str, amount: float,
                   price: Optional[float] = None, order_type: str = "market") -> OrderResult:
        """通用下单接口（套利引擎使用）"""
        return self._exchange.place_order(symbol, side, amount, price, order_type)

    def get_order_status(self, order_id: str, symbol: str) -> OrderResult:
        """查询订单状态（套利引擎使用）"""
        return self._exchange.get_order_status(order_id, symbol)

    # ========== 辅助方法 ==========

    def fetch_multi_timeframe_data(self, timeframes: List[str]) -> Dict[str, pd.DataFrame]:
        """获取多时间周期数据"""
        return self._exchange.fetch_multi_timeframe_data(timeframes)

    def get_exchange_name(self) -> str:
        """获取交易所名称"""
        return self._exchange.get_exchange_name()

    def get_last_order_result(self) -> Optional[OrderResult]:
        """
        获取最后一次订单的完整结果

        用于需要访问 order_id 等详细信息的场景
        """
        return getattr(self, '_last_order_result', None)
