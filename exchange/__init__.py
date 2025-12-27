"""
多交易所框架
支持Bitget、Binance、OKX等交易所的统一接口
"""

from .interface import ExchangeInterface, TickerData, PositionData, OrderResult
from .factory import ExchangeFactory
from .manager import ExchangeManager
from .errors import (
    ExchangeError,
    NetworkError,
    AuthenticationError,
    RateLimitError,
    InsufficientBalanceError
)

# 导入适配器
from .adapters import BitgetAdapter, BinanceAdapter, OKXAdapter

# 注册适配器到工厂
ExchangeFactory.register('bitget', BitgetAdapter)
ExchangeFactory.register('binance', BinanceAdapter)
ExchangeFactory.register('okx', OKXAdapter)

__all__ = [
    'ExchangeInterface',
    'TickerData',
    'PositionData',
    'OrderResult',
    'ExchangeFactory',
    'ExchangeManager',
    'ExchangeError',
    'NetworkError',
    'AuthenticationError',
    'RateLimitError',
    'InsufficientBalanceError',
    'BitgetAdapter',
    'BinanceAdapter',
    'OKXAdapter',
]
