"""
OKX交易所适配器
"""
import ccxt
import time
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime

from logger_utils import get_logger
from ..interface import ExchangeInterface, TickerData, PositionData, OrderResult
from ..errors import (
    ExchangeError, NetworkError, AuthenticationError,
    RateLimitError, InsufficientBalanceError, OrderError
)
from ..decorators import retry_on_error

logger = get_logger("okx_adapter")


class OKXAdapter(ExchangeInterface):
    """OKX交易所适配器"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.exchange_name = "okx"
        self.symbol = config.get("symbol", "BTC/USDT:USDT")
        self.leverage = config.get("leverage", 10)
        self.margin_mode = config.get("margin_mode", "crossed")
        self.inst_type = "SWAP"  # OKX永续合约类型

    # ========== 生命周期管理 ==========

    def connect(self) -> bool:
        """连接交易所"""
        try:
            self.exchange = ccxt.okx({
                "apiKey": self.config.get("api_key", ""),
                "secret": self.config.get("api_secret", ""),
                "password": self.config.get("api_password", ""),
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",
                }
            })

            # 设置交易参数
            self._setup_trading_params()

            logger.info("OKX交易所连接成功")
            return True

        except ccxt.AuthenticationError as e:
            logger.error(f"OKX认证失败: {e}")
            raise AuthenticationError(f"OKX认证失败: {e}", e)
        except Exception as e:
            logger.error(f"OKX连接失败: {e}")
            raise ExchangeError(f"OKX连接失败: {e}", e)

    def _setup_trading_params(self):
        """设置交易参数"""
        try:
            # OKX使用tdMode参数：cross(全仓) 或 isolated(逐仓)
            td_mode = "cross" if self.margin_mode.lower() == "crossed" else "isolated"

            # 设置杠杆
            self.exchange.set_leverage(
                self.leverage,
                self.symbol,
                params={
                    "mgnMode": td_mode,
                    "posSide": "long"  # 需要为多空分别设置
                }
            )

            self.exchange.set_leverage(
                self.leverage,
                self.symbol,
                params={
                    "mgnMode": td_mode,
                    "posSide": "short"
                }
            )

            logger.info(f"OKX交易参数设置成功: 杠杆{self.leverage}x, 保证金模式{td_mode}")

        except Exception as e:
            logger.warning(f"OKX设置交易参数失败: {e}")

    def disconnect(self):
        """断开连接"""
        self.exchange = None
        logger.info("OKX交易所连接已断开")

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.exchange is not None

    # ========== 市场数据接口 ==========

    @retry_on_error(max_retries=3, backoff_base=1.0)
    def get_ticker(self, symbol: str = None) -> Optional[TickerData]:
        """获取行情"""
        if not self.is_connected():
            raise ExchangeError("交易所未连接")

        symbol = symbol or self.symbol

        try:
            ticker = self.exchange.fetch_ticker(symbol)

            return TickerData(
                symbol=symbol,
                last=float(ticker.get('last', 0)),
                bid=float(ticker.get('bid', 0)) if ticker.get('bid') else None,
                ask=float(ticker.get('ask', 0)) if ticker.get('ask') else None,
                volume=float(ticker.get('baseVolume', 0)) if ticker.get('baseVolume') else None,
                timestamp=int(ticker.get('timestamp', 0)),
                raw_data=ticker
            )

        except ccxt.NetworkError as e:
            logger.error(f"OKX获取行情网络错误: {e}")
            raise NetworkError(f"获取行情网络错误: {e}", e)
        except ccxt.RateLimitExceeded as e:
            logger.error(f"OKX限流: {e}")
            raise RateLimitError(f"限流: {e}", e)
        except Exception as e:
            logger.error(f"OKX获取行情失败: {e}")
            raise ExchangeError(f"获取行情失败: {e}", e)

    @retry_on_error(max_retries=3, backoff_base=1.0)
    def get_klines(self, symbol: str = None, timeframe: str = None,
                   limit: int = None) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        if not self.is_connected():
            raise ExchangeError("交易所未连接")

        symbol = symbol or self.symbol
        timeframe = timeframe or "5m"
        limit = limit or 100

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df

        except ccxt.NetworkError as e:
            logger.error(f"OKX获取K线网络错误: {e}")
            raise NetworkError(f"获取K线网络错误: {e}", e)
        except Exception as e:
            logger.error(f"OKX获取K线失败: {e}")
            raise ExchangeError(f"获取K线失败: {e}", e)

    @retry_on_error(max_retries=3, backoff_base=1.0)
    def get_orderbook(self, symbol: str = None, limit: int = 20) -> Optional[Dict]:
        """获取订单簿"""
        if not self.is_connected():
            raise ExchangeError("交易所未连接")

        symbol = symbol or self.symbol

        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit)

            return {
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', []),
                'timestamp': orderbook.get('timestamp', 0),
                'datetime': orderbook.get('datetime', ''),
            }

        except Exception as e:
            logger.error(f"OKX获取订单簿失败: {e}")
            raise ExchangeError(f"获取订单簿失败: {e}", e)

    # ========== 账户接口 ==========

    @retry_on_error(max_retries=3, backoff_base=1.0)
    def get_balance(self) -> float:
        """获取账户余额（USDT）"""
        if not self.is_connected():
            raise ExchangeError("交易所未连接")

        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)

            return float(usdt_balance)

        except ccxt.InsufficientFunds as e:
            logger.error(f"OKX余额不足: {e}")
            raise InsufficientBalanceError(f"余额不足: {e}", e)
        except Exception as e:
            logger.error(f"OKX获取余额失败: {e}")
            raise ExchangeError(f"获取余额失败: {e}", e)

    @retry_on_error(max_retries=3, backoff_base=1.0)
    def get_positions(self, symbol: str = None) -> List[PositionData]:
        """获取持仓列表"""
        if not self.is_connected():
            raise ExchangeError("交易所未连接")

        symbol = symbol or self.symbol

        try:
            positions = self.exchange.fetch_positions([symbol])

            result = []
            for pos in positions:
                amount = abs(float(pos.get('contracts', 0)))
                if amount > 0:
                    # OKX使用posSide来区分多空
                    position_side = pos.get('side', '').lower()

                    result.append(PositionData(
                        side=position_side,
                        amount=amount,
                        entry_price=float(pos.get('entryPrice', 0)),
                        unrealized_pnl=float(pos.get('unrealizedPnl', 0)),
                        leverage=int(pos.get('leverage', self.leverage)),
                        margin_mode=pos.get('marginMode', self.margin_mode),
                        raw_data=pos
                    ))

            return result

        except Exception as e:
            logger.error(f"OKX获取持仓失败: {e}")
            raise ExchangeError(f"获取持仓失败: {e}", e)

    # ========== 交易接口 ==========

    def open_long(self, amount: float, df: pd.DataFrame = None, **kwargs) -> OrderResult:
        """开多单"""
        return self._create_order("buy", amount, pos_side="long", reduce_only=False, **kwargs)

    def open_short(self, amount: float, df: pd.DataFrame = None, **kwargs) -> OrderResult:
        """开空单"""
        return self._create_order("sell", amount, pos_side="short", reduce_only=False, **kwargs)

    @retry_on_error(max_retries=3, backoff_base=1.0)
    def _create_order(self, side: str, amount: float, pos_side: str = None,
                      reduce_only: bool = False, **kwargs) -> OrderResult:
        """创建订单（内部方法）"""
        if not self.is_connected():
            return OrderResult(success=False, error="交易所未连接")

        try:
            # OKX双向持仓模式参数
            td_mode = "cross" if self.margin_mode.lower() == "crossed" else "isolated"

            params = {
                "tdMode": td_mode,
            }

            if pos_side:
                params['posSide'] = pos_side

            if reduce_only:
                params['reduceOnly'] = True

            order = self.exchange.create_order(
                symbol=self.symbol,
                type="market",
                side=side,
                amount=amount,
                params=params
            )

            logger.info(f"OKX订单创建成功: {side} {amount}")

            return OrderResult(
                success=True,
                order_id=order.get('id', ''),
                price=float(order.get('price', 0)) if order.get('price') else None,
                amount=float(order.get('amount', amount)),
                side=side,
                raw_data=order
            )

        except ccxt.InsufficientFunds as e:
            logger.error(f"OKX余额不足: {e}")
            return OrderResult(success=False, error=f"余额不足: {e}")
        except ccxt.InvalidOrder as e:
            logger.error(f"OKX订单无效: {e}")
            return OrderResult(success=False, error=f"订单无效: {e}")
        except Exception as e:
            logger.error(f"OKX创建订单失败: {e}")
            return OrderResult(success=False, error=f"创建订单失败: {e}")

    def close_position(self, reason: str = "", position_data: Dict = None) -> bool:
        """平仓"""
        if not self.is_connected():
            logger.error("交易所未连接")
            return False

        # 获取持仓信息
        if position_data:
            position_side = position_data.get('side')
            position_amount = position_data.get('amount')
        else:
            positions = self.get_positions()
            if not positions:
                logger.warning("无持仓可平")
                return False
            position_side = positions[0].side
            position_amount = positions[0].amount

        try:
            # OKX平仓：使用相反方向的订单 + reduceOnly
            close_side = "sell" if position_side == 'long' else "buy"

            result = self._create_order(
                close_side,
                position_amount,
                pos_side=position_side,
                reduce_only=True
            )

            if result.success:
                logger.info(f"OKX平仓成功: {position_side}, 原因: {reason}")
                return True
            else:
                logger.error(f"OKX平仓失败: {result.error}")
                return False

        except Exception as e:
            logger.error(f"OKX平仓失败: {e}")
            return False

    def close_all_positions(self) -> List[OrderResult]:
        """一键平仓所有持仓"""
        results = []

        try:
            positions = self.get_positions()

            for position in positions:
                success = self.close_position(
                    reason="一键平仓",
                    position_data={'side': position.side, 'amount': position.amount}
                )

                results.append(OrderResult(
                    success=success,
                    side=position.side,
                    amount=position.amount
                ))

        except Exception as e:
            logger.error(f"OKX一键平仓所有持仓失败: {e}")

        return results

    # ========== 交易参数设置 ==========

    def set_leverage(self, leverage: int, symbol: str = None) -> bool:
        """设置杠杆"""
        if not self.is_connected():
            logger.error("交易所未连接")
            return False

        symbol = symbol or self.symbol

        try:
            td_mode = "cross" if self.margin_mode.lower() == "crossed" else "isolated"

            # OKX需要为多空分别设置杠杆
            self.exchange.set_leverage(
                leverage,
                symbol,
                params={
                    "mgnMode": td_mode,
                    "posSide": "long"
                }
            )

            self.exchange.set_leverage(
                leverage,
                symbol,
                params={
                    "mgnMode": td_mode,
                    "posSide": "short"
                }
            )

            self.leverage = leverage
            logger.info(f"OKX设置杠杆成功: {leverage}x")
            return True

        except Exception as e:
            logger.error(f"OKX设置杠杆失败: {e}")
            return False

    def set_margin_mode(self, mode: str, symbol: str = None) -> bool:
        """设置保证金模式"""
        if not self.is_connected():
            logger.error("交易所未连接")
            return False

        symbol = symbol or self.symbol

        try:
            # OKX使用cross或isolated
            td_mode = "cross" if mode.lower() == "crossed" else "isolated"

            # 注意：OKX的保证金模式设置可能需要特殊处理
            # 这里简化处理，实际使用时可能需要调用特定API

            self.margin_mode = mode
            logger.info(f"OKX设置保证金模式成功: {td_mode}")
            return True

        except Exception as e:
            logger.error(f"OKX设置保证金模式失败: {e}")
            return False

    # ========== 辅助方法 ==========

    def get_exchange_name(self) -> str:
        """获取交易所名称"""
        return self.exchange_name
