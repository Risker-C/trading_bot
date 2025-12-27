"""
交易所异常类定义
"""


class ExchangeError(Exception):
    """交易所错误基类"""

    def __init__(self, message: str, raw_error: Exception = None):
        super().__init__(message)
        self.raw_error = raw_error


class NetworkError(ExchangeError):
    """网络错误"""
    pass


class AuthenticationError(ExchangeError):
    """认证错误"""
    pass


class RateLimitError(ExchangeError):
    """限流错误"""
    pass


class InsufficientBalanceError(ExchangeError):
    """余额不足错误"""
    pass


class OrderError(ExchangeError):
    """订单错误"""
    pass


class PositionError(ExchangeError):
    """持仓错误"""
    pass
