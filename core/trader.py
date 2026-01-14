"""
交易执行器 - 增强版
"""
import ccxt
import asyncio
import ccxt.async_support as ccxt_async
import time
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import pandas as pd

from config.settings import settings as config
from utils.logger_utils import get_logger, db
from strategies.strategies import (
    Signal, TradeSignal, get_strategy, analyze_all_strategies,
    get_consensus_signal, STRATEGY_MAP
)
from risk.risk_manager import (
    RiskManager, PositionInfo, PositionBuilder,
    PositionCloser, DrawdownController
)
from strategies.indicators import IndicatorCalculator
from risk.error_backoff_controller import get_backoff_controller
from risk.liquidity_validator import get_liquidity_validator

logger = get_logger("trader")


class HealthMonitor:
    """健康监控器 - 集成错误退避控制器"""

    def __init__(self, exchange_name: str = "bitget"):
        self.exchange_name = exchange_name
        self.api_errors = 0
        self.last_heartbeat = datetime.now()
        self.last_successful_request = datetime.now()
        self.is_healthy = True
        self.reconnect_count = 0

        # 集成错误退避控制器
        if config.ENABLE_ERROR_BACKOFF:
            self.backoff_controller = get_backoff_controller()
        else:
            self.backoff_controller = None

    def record_success(self):
        """记录成功请求"""
        self.api_errors = 0
        self.last_successful_request = datetime.now()
        self.is_healthy = True

    def record_error(self, error: Exception, error_code: str = ""):
        """
        记录错误并触发退避

        Args:
            error: 异常对象
            error_code: 错误代码（可选）
        """
        self.api_errors += 1
        error_msg = str(error)
        logger.error(f"API错误 ({self.api_errors}): {error_msg}")

        # 使用退避控制器
        if self.backoff_controller:
            # 尝试从错误消息中提取错误代码
            if not error_code:
                error_code = self._extract_error_code(error_msg)

            self.backoff_controller.register_error(
                exchange=self.exchange_name,
                error_code=error_code,
                error_message=error_msg
            )

        if self.api_errors >= config.MAX_API_ERRORS:
            self.is_healthy = False
            logger.error(f"连续 {self.api_errors} 次错误，标记为不健康")

    def is_paused(self) -> bool:
        """检查是否处于退避暂停状态"""
        if self.backoff_controller:
            return self.backoff_controller.is_paused(self.exchange_name)
        return False

    def check_heartbeat(self) -> bool:
        """检查心跳"""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        return elapsed < config.HEARTBEAT_INTERVAL * 2

    def update_heartbeat(self):
        """更新心跳"""
        self.last_heartbeat = datetime.now()

    def should_reconnect(self) -> bool:
        """是否需要重连"""
        if not config.AUTO_RECONNECT:
            return False

        if not self.is_healthy and self.api_errors >= config.MAX_API_ERRORS:
            return True

        # 超过一定时间没有成功请求
        elapsed = (datetime.now() - self.last_successful_request).total_seconds()
        return elapsed > config.HEALTH_CHECK_INTERVAL

    def _extract_error_code(self, error_message: str) -> str:
        """从错误消息中提取错误代码"""
        error_msg_lower = error_message.lower()

        # 常见错误代码模式
        if "429" in error_message or "rate limit" in error_msg_lower:
            return "429"
        elif "21104" in error_message or "nonce" in error_msg_lower:
            return "21104"
        elif "timeout" in error_msg_lower:
            return "timeout"
        elif "network" in error_msg_lower or "connection" in error_msg_lower:
            return "network"
        else:
            return "api"


class BitgetTrader:
    """Bitget 交易执行器"""
    
    def __init__(self):
        self.exchange = None
        self.risk_manager = RiskManager(self)
        self.drawdown_controller = DrawdownController()
        self.health_monitor = HealthMonitor()

        # 流动性验证器
        self.liquidity_validator = get_liquidity_validator()

        # 分批建仓/平仓管理
        self.position_builder: Optional[PositionBuilder] = None
        self.position_closer: Optional[PositionCloser] = None

        # 多时间周期数据缓存
        self.timeframe_data: Dict[str, pd.DataFrame] = {}

        # 初始化
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化交易所连接"""
        try:
            self.exchange = ccxt.bitget({
                "apiKey": config.EXCHANGE_CONFIG["api_key"],
                "secret": config.EXCHANGE_CONFIG["api_secret"],
                "password": config.EXCHANGE_CONFIG["api_password"],
                "enableRateLimit": True,
                "options": {
                    "defaultType": "swap",
                }
            })
            
            # 设置杠杆和保证金模式
            self._setup_trading_params()
            
            self.health_monitor.record_success()
            logger.info("交易所连接成功")
            
        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"交易所连接失败: {e}")
            raise
    
    def _setup_trading_params(self):
        """设置交易参数"""
        try:
            # 设置杠杆
            self.exchange.set_leverage(
                config.LEVERAGE,
                config.SYMBOL,
                params={"productType": config.PRODUCT_TYPE}
            )
            
            # 设置保证金模式
            self.exchange.set_margin_mode(
                config.MARGIN_MODE,
                config.SYMBOL,
                params={"productType": config.PRODUCT_TYPE}
            )
            
            logger.info(f"杠杆: {config.LEVERAGE}x, 保证金模式: {config.MARGIN_MODE}")
            
        except Exception as e:
            logger.warning(f"设置交易参数失败: {e}")
    
    def reconnect(self):
        """重新连接"""
        logger.info("尝试重新连接...")
        self.health_monitor.reconnect_count += 1
        
        time.sleep(config.API_ERROR_COOLDOWN)
        
        try:
            self._init_exchange()
            logger.info(f"重连成功 (第 {self.health_monitor.reconnect_count} 次)")
        except Exception as e:
            logger.error(f"重连失败: {e}")
    
    # ==================== 数据获取 ====================
    
    def fetch_ohlcv(
        self,
        symbol: str = None,
        timeframe: str = None,
        limit: int = None
    ) -> Optional[pd.DataFrame]:
        """获取K线数据"""
        symbol = symbol or config.SYMBOL
        timeframe = timeframe or config.TIMEFRAME
        limit = limit or config.KLINE_LIMIT

        try:
            ohlcv = self.exchange.fetch_ohlcv(
                symbol, timeframe, limit=limit,
                params={"productType": config.PRODUCT_TYPE}
            )

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            self.health_monitor.record_success()

            return df

        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"获取K线失败: {e}")
            return None

    def get_klines(self, symbol: str = None, timeframe: str = None, limit: int = None) -> Optional[pd.DataFrame]:
        """获取K线数据（兼容bot.py）"""
        return self.fetch_ohlcv(symbol, timeframe, limit)
    
    def fetch_multi_timeframe_data(self) -> Dict[str, pd.DataFrame]:
        """
        获取多时间周期数据
        
        根据配置 USE_ASYNC_DATA_FETCH 自动选择同步或异步方式：
        - 异步模式：并发获取，速度快（3-5倍提升）
        - 同步模式：顺序获取，兼容性好
        
        Returns:
            Dict[str, pd.DataFrame]: 时间周期到数据的映射
        """
        if not config.MULTI_TIMEFRAME_ENABLED:
            return {}
        
        # 根据配置选择同步或异步方式
        if config.USE_ASYNC_DATA_FETCH:
            logger.info("使用异步模式获取多时间周期数据")
            data = self._run_async(self.fetch_multi_timeframe_data_async())
        else:
            logger.info("使用同步模式获取多时间周期数据")
            start_time = time.time()
            
            data = {}
            for tf in config.TIMEFRAMES:
                df = self.fetch_ohlcv(timeframe=tf)
                if df is not None:
                    data[tf] = df
                time.sleep(0.5)  # 避免频率限制
            
            elapsed = time.time() - start_time
            logger.info(
                f"同步获取多时间周期数据完成: "
                f"{len(data)}/{len(config.TIMEFRAMES)} 个周期, "
                f"耗时 {elapsed:.2f}s"
            )
        
        self.timeframe_data = data
        return data
    

    # ==================== 异步数据获取方法 ====================
    
    def _run_async(self, coro):
        """
        运行异步协程的辅助方法
        
        Args:
            coro: 异步协程对象
            
        Returns:
            协程的返回值
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环已在运行，创建新的事件循环
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # 如果没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
    
    async def fetch_ohlcv_async(
        self,
        symbol: str = None,
        timeframe: str = None,
        limit: int = None,
        exchange_async: ccxt_async.Exchange = None
    ) -> Optional[pd.DataFrame]:
        """
        异步获取K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            limit: K线数量
            exchange_async: 异步交易所实例（可选）
            
        Returns:
            DataFrame: K线数据
        """
        symbol = symbol or config.SYMBOL
        timeframe = timeframe or config.TIMEFRAME
        limit = limit or config.KLINE_LIMIT
        
        # 如果没有提供异步交易所实例，创建临时实例
        close_exchange = False
        if exchange_async is None:
            exchange_class = getattr(ccxt_async, config.ACTIVE_EXCHANGE.lower())
            exchange_async = exchange_class({
                "apiKey": config.API_KEY,
                "secret": config.API_SECRET,
                "password": config.EXCHANGE_CONFIG.get("api_password", ""),
                "enableRateLimit": True,
                "options": {"defaultType": "swap"}
            })
            close_exchange = True
        
        try:
            ohlcv = await exchange_async.fetch_ohlcv(
                symbol, timeframe, limit=limit,
                params={"productType": config.PRODUCT_TYPE}
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"异步获取K线失败 [{timeframe}]: {e}")
            return None
        finally:
            if close_exchange:
                await exchange_async.close()
    
    async def fetch_multi_timeframe_data_async(self) -> Dict[str, pd.DataFrame]:
        """
        异步并发获取多时间周期数据
        
        使用 asyncio.gather 并发获取所有时间周期的数据，
        相比同步方法可以显著提升性能（3-5倍速度提升）
        
        Returns:
            Dict[str, pd.DataFrame]: 时间周期到数据的映射
        """
        if not config.MULTI_TIMEFRAME_ENABLED:
            return {}
        
        start_time = time.time()
        
        # 创建异步交易所实例
        exchange_class = getattr(ccxt_async, getattr(config, 'ACTIVE_EXCHANGE', 'bitget').lower())
        exchange_async = exchange_class({
            "apiKey": getattr(config, 'API_KEY', ''),
            "secret": getattr(config, 'API_SECRET', ''),
            "password": getattr(config, 'EXCHANGE_CONFIG', {}).get("api_password", ""),
            "enableRateLimit": True,
            "options": {"defaultType": "swap"}
        })
        
        try:
            # 并发获取所有时间周期的数据
            tasks = [
                self.fetch_ohlcv_async(
                    timeframe=tf,
                    exchange_async=exchange_async
                )
                for tf in config.TIMEFRAMES
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 构建结果字典
            data = {}
            for tf, result in zip(config.TIMEFRAMES, results):
                if isinstance(result, Exception):
                    logger.error(f"获取 {tf} 数据失败: {result}")
                elif result is not None:
                    data[tf] = result
            
            elapsed = time.time() - start_time
            logger.info(
                f"异步获取多时间周期数据完成: "
                f"{len(data)}/{len(config.TIMEFRAMES)} 个周期, "
                f"耗时 {elapsed:.2f}s"
            )
            
            return data
            
        except Exception as e:
            logger.error(f"异步获取多时间周期数据失败: {e}")
            return {}
        finally:
            await exchange_async.close()

    def get_balance(self) -> float:
        """获取可用余额"""
        try:
            balance = self.exchange.fetch_balance(
                params={"productType": config.PRODUCT_TYPE}
            )
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            
            self.health_monitor.record_success()
            
            return float(usdt_balance)
            
        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"获取余额失败: {e}")
            return 0
    
    def get_position(self) -> Optional[Dict]:
        """获取当前持仓"""
        try:
            positions = self.exchange.fetch_positions(
                symbols=[config.SYMBOL],
                params={"productType": config.PRODUCT_TYPE}
            )

            self.health_monitor.record_success()

            for pos in positions:
                amount = float(pos.get('contracts', 0))
                if amount > 0:
                    return {
                        'side': pos.get('side'),
                        'amount': amount,
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'liquidation_price': float(pos.get('liquidationPrice', 0)),
                    }

            return None

        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"获取持仓失败: {e}")
            return None

    def get_positions(self) -> list:
        """获取持仓列表（兼容bot.py）"""
        position = self.get_position()
        return [position] if position else []

    def get_ticker(self, symbol: str = None) -> Optional[Dict]:
        """获取最新价格"""
        symbol = symbol or config.SYMBOL
        
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            self.health_monitor.record_success()
            
            return {
                'last': float(ticker.get('last', 0)),
                'bid': float(ticker.get('bid', 0)),
                'ask': float(ticker.get('ask', 0)),
                'volume': float(ticker.get('baseVolume', 0)),
            }
            
        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"获取价格失败: {e}")
            return None
    
    def sync_position(self):
        """同步持仓状态"""
        exchange_pos = self.get_position()

        if exchange_pos:
            if self.risk_manager.position is None:
                # 有持仓但本地没有记录，同步
                logger.info(f"同步持仓: {exchange_pos}")

                # 尝试从数据库恢复历史价格信息
                snapshot = db.get_latest_position_snapshot(config.SYMBOL)
                highest_price = None
                lowest_price = None
                entry_time = None

                if snapshot:
                    # 验证快照是否与当前持仓匹配
                    if (snapshot['side'] == exchange_pos['side'] and
                        abs(snapshot['entry_price'] - exchange_pos['entry_price']) < 1.0):
                        highest_price = snapshot['highest_price']
                        lowest_price = snapshot['lowest_price']
                        if snapshot['entry_time']:
                            from dateutil import parser
                            entry_time = parser.parse(snapshot['entry_time'])
                        logger.info(f"✅ 从数据库恢复历史价格:")
                        logger.info(f"   开仓价: {exchange_pos['entry_price']:.2f}")
                        logger.info(f"   最高价: {highest_price:.2f} (涨幅: {(highest_price/exchange_pos['entry_price']-1)*100:+.2f}%)")
                        logger.info(f"   最低价: {lowest_price:.2f} (跌幅: {(lowest_price/exchange_pos['entry_price']-1)*100:+.2f}%)")
                        logger.info(f"   开仓时间: {entry_time if entry_time else 'N/A'}")
                    else:
                        logger.warning(f"⚠️  数据库快照与交易所持仓不匹配:")
                        logger.warning(f"   数据库: {snapshot['side']} @ {snapshot['entry_price']:.2f}")
                        logger.warning(f"   交易所: {exchange_pos['side']} @ {exchange_pos['entry_price']:.2f}")
                        logger.warning(f"   使用默认值（开仓价作为历史价格）")
                else:
                    logger.info(f"📝 数据库中无历史快照，使用默认值")

                self.risk_manager.set_position(
                    side=exchange_pos['side'],
                    amount=exchange_pos['amount'],
                    entry_price=exchange_pos['entry_price'],
                    highest_price=highest_price,
                    lowest_price=lowest_price,
                    entry_time=entry_time
                )
            else:
                # 更新价格信息
                ticker = self.get_ticker()
                if ticker:
                    self.risk_manager.position.update_price(ticker['last'])
        else:
            # 没有持仓
            if self.risk_manager.position is not None:
                logger.info("持仓已清除，同步本地状态")
                self.risk_manager.clear_position()
    
    # ==================== 订单执行 ====================
    
    def create_market_order(
        self,
        side: str,
        amount: float,
        reduce_only: bool = False
    ) -> Optional[Dict]:
        """创建市价单"""
        try:
            # 流动性验证（仅在开仓时检查）
            if not reduce_only and config.LIQUIDITY_VALIDATION_ENABLED:
                ticker = self.get_ticker()
                if ticker:
                    current_price = ticker['last']
                    is_buy = (side == 'buy')
                    liquidity_pass, liquidity_reason, liquidity_details = self.liquidity_validator.validate_liquidity(
                        ticker=ticker,
                        order_amount=amount,
                        order_price=current_price,
                        is_buy=is_buy
                    )

                    if not liquidity_pass:
                        logger.warning(f"❌ 市价单流动性验证失败: {liquidity_reason}")
                        return None

                    logger.debug(f"✅ 市价单流动性验证通过")

            # 双向持仓模式：平仓时使用 tradeSide="close"
            params = {
                "productType": config.PRODUCT_TYPE,
                "tradeSide": "open" if not reduce_only else "close",
            }

            order = self.exchange.create_order(
                symbol=config.SYMBOL,
                type="market",
                side=side,
                amount=amount,
                params=params
            )

            self.health_monitor.record_success()
            logger.info(f"订单创建成功: {side} {amount} @ market")

            return order

        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"订单创建失败: {e}")
            return None

    def create_limit_order(
        self,
        side: str,
        amount: float,
        price: float,
        reduce_only: bool = False
    ) -> Optional[Dict]:
        """创建限价单（Maker订单）

        Args:
            side: 方向 'buy' 或 'sell'
            amount: 数量
            price: 限价价格
            reduce_only: 是否只减仓

        Returns:
            订单信息或None
        """
        try:
            # 流动性验证（仅在开仓时检查）
            if not reduce_only and config.LIQUIDITY_VALIDATION_ENABLED:
                ticker = self.get_ticker()
                if ticker:
                    is_buy = (side == 'buy')
                    liquidity_pass, liquidity_reason, liquidity_details = self.liquidity_validator.validate_liquidity(
                        ticker=ticker,
                        order_amount=amount,
                        order_price=price,
                        is_buy=is_buy
                    )

                    if not liquidity_pass:
                        logger.warning(f"❌ 限价单流动性验证失败: {liquidity_reason}")
                        return None

                    logger.debug(f"✅ 限价单流动性验证通过")

            params = {
                "productType": config.PRODUCT_TYPE,
                "tradeSide": "open" if not reduce_only else "close",
            }

            order = self.exchange.create_order(
                symbol=config.SYMBOL,
                type="limit",
                side=side,
                amount=amount,
                price=price,
                params=params
            )

            self.health_monitor.record_success()
            logger.info(f"限价单创建成功: {side} {amount} @ {price:.2f}")

            return order

        except Exception as e:
            self.health_monitor.record_error(e)
            logger.error(f"限价单创建失败: {e}")
            return None

    def wait_for_order_fill(self, order_id: str, timeout: float = None) -> Tuple[bool, Optional[Dict]]:
        """等待订单成交

        Args:
            order_id: 订单ID
            timeout: 超时时间（秒），默认使用配置中的值

        Returns:
            (是否成交, 订单详情)
        """
        if timeout is None:
            timeout = config.MAKER_ORDER_TIMEOUT

        start_time = time.time()
        check_interval = config.MAKER_ORDER_CHECK_INTERVAL

        logger.info(f"等待订单成交: {order_id}, 超时时间: {timeout}秒")

        while time.time() - start_time < timeout:
            try:
                order = self.exchange.fetch_order(order_id, config.SYMBOL)
                status = order.get('status', '')

                if status == 'closed' or status == 'filled':
                    logger.info(f"订单已成交: {order_id}")
                    return True, order
                elif status == 'canceled':
                    logger.warning(f"订单已取消: {order_id}")
                    return False, order

                time.sleep(check_interval)

            except Exception as e:
                logger.error(f"查询订单状态失败: {e}")
                time.sleep(check_interval)

        logger.warning(f"订单等待超时: {order_id}")
        return False, None

    def cancel_order(self, order_id: str) -> bool:
        """取消订单

        Args:
            order_id: 订单ID

        Returns:
            是否成功取消
        """
        try:
            self.exchange.cancel_order(order_id, config.SYMBOL)
            logger.info(f"订单已取消: {order_id}")
            return True
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            return False

    def _calculate_dynamic_maker_params(
        self,
        signal_strength: float,
        volatility: float
    ) -> Tuple[float, float]:
        """根据信号强度和波动率计算动态Maker订单参数

        Args:
            signal_strength: 信号强度 (0-1)
            volatility: 波动率 (百分比)

        Returns:
            (超时时间, 价格偏移量)
        """
        # 基础参数
        base_timeout = config.MAKER_ORDER_TIMEOUT
        base_offset = config.MAKER_PRICE_OFFSET

        # 根据波动率调整
        if volatility > config.HIGH_VOLATILITY_THRESHOLD:
            # 高波动：缩短超时，增大偏移
            timeout = config.MAKER_HIGH_VOL_TIMEOUT
            offset = config.MAKER_HIGH_VOL_OFFSET
            logger.debug(f"高波动({volatility:.2%})：超时{timeout}秒，偏移{offset*100:.3f}%")
        elif volatility < config.LOW_VOLATILITY_THRESHOLD:
            # 低波动：延长超时，减小偏移
            timeout = config.MAKER_LOW_VOL_TIMEOUT
            offset = config.MAKER_LOW_VOL_OFFSET
            logger.debug(f"低波动({volatility:.2%})：超时{timeout}秒，偏移{offset*100:.3f}%")
        else:
            # 正常波动：使用基础参数
            timeout = base_timeout
            offset = base_offset
            logger.debug(f"正常波动({volatility:.2%})：超时{timeout}秒，偏移{offset*100:.3f}%")

        # 根据信号强度微调超时时间
        if signal_strength > config.MAKER_OPTIMAL_SIGNAL_STRENGTH:
            # 强信号：可以等更久
            timeout *= 1.2
            logger.debug(f"强信号({signal_strength:.2f})：超时延长至{timeout:.1f}秒")
        elif signal_strength < 0.7:
            # 中等信号：缩短等待
            timeout *= 0.8
            logger.debug(f"中等信号({signal_strength:.2f})：超时缩短至{timeout:.1f}秒")

        return timeout, offset

    def create_smart_order(
        self,
        side: str,
        amount: float,
        reduce_only: bool = False,
        signal_strength: float = 1.0,
        volatility: float = 0.03
    ) -> Optional[Dict]:
        """智能下单：根据信号强度和波动率动态选择Maker或Taker订单

        Args:
            side: 方向 'buy' 或 'sell'
            amount: 数量
            reduce_only: 是否只减仓
            signal_strength: 信号强度 (0-1)
            volatility: 波动率 (百分比)

        Returns:
            订单信息或None
        """
        # 如果未启用Maker订单，直接使用市价单
        if not config.USE_MAKER_ORDER:
            logger.info("使用市价单（Taker）")
            return self.create_market_order(side, amount, reduce_only)

        # 动态Maker订单逻辑
        if config.ENABLE_DYNAMIC_MAKER:
            # 1. 信号强度过滤
            if signal_strength < config.MAKER_MIN_SIGNAL_STRENGTH:
                logger.info(f"信号强度{signal_strength:.2f}低于阈值{config.MAKER_MIN_SIGNAL_STRENGTH}，使用市价单")
                return self.create_market_order(side, amount, reduce_only)

            # 2. 极端波动检测
            if config.MAKER_DISABLE_ON_EXTREME_VOL and volatility > config.MAKER_EXTREME_VOL_THRESHOLD:
                logger.info(f"极端波动{volatility:.2%}超过阈值{config.MAKER_EXTREME_VOL_THRESHOLD:.2%}，使用市价单")
                return self.create_market_order(side, amount, reduce_only)

        # 获取当前价格
        ticker = self.get_ticker()
        if not ticker:
            logger.error("无法获取当前价格，降级为市价单")
            return self.create_market_order(side, amount, reduce_only)

        current_price = ticker['last']

        # 流动性验证（仅在开仓时检查）
        if not reduce_only and config.LIQUIDITY_VALIDATION_ENABLED:
            is_buy = (side == 'buy')
            liquidity_pass, liquidity_reason, liquidity_details = self.liquidity_validator.validate_liquidity(
                ticker=ticker,
                order_amount=amount,
                order_price=current_price,
                is_buy=is_buy
            )

            if not liquidity_pass:
                logger.warning(f"❌ 流动性验证失败: {liquidity_reason}")
                logger.debug(f"流动性详情: {liquidity_details}")
                return None

            logger.debug(f"✅ 流动性验证通过: {liquidity_reason}")

        # 动态计算Maker订单参数
        if config.ENABLE_DYNAMIC_MAKER:
            timeout, offset = self._calculate_dynamic_maker_params(signal_strength, volatility)
        else:
            timeout = config.MAKER_ORDER_TIMEOUT
            offset = config.MAKER_PRICE_OFFSET

        # 计算挂单价格（使用动态偏移量）
        if side == 'buy':
            # 做多：挂单价格略低于市价
            limit_price = current_price * (1 - offset)
        else:
            # 做空：挂单价格略高于市价
            limit_price = current_price * (1 + offset)

        logger.info(f"尝试Maker订单: {side} {amount} @ {limit_price:.2f} (市价: {current_price:.2f}, 偏移: {offset*100:.3f}%)")

        # 创建限价单
        order = self.create_limit_order(side, amount, limit_price, reduce_only)
        if not order:
            logger.warning("限价单创建失败，降级为市价单")
            return self.create_market_order(side, amount, reduce_only)

        order_id = order.get('id', '')
        if not order_id:
            logger.warning("无法获取订单ID，降级为市价单")
            return self.create_market_order(side, amount, reduce_only)

        # 等待订单成交（使用动态超时时间）
        filled, order_detail = self.wait_for_order_fill(order_id, timeout)

        if filled:
            logger.info(f"✅ Maker订单成交，节省手续费67%")
            return order_detail

        # 超时未成交，取消订单
        logger.warning("Maker订单超时未成交")
        self.cancel_order(order_id)

        # 根据配置决定是否降级为市价单
        if config.MAKER_AUTO_FALLBACK_TO_MARKET:
            logger.info("自动降级为市价单")
            return self.create_market_order(side, amount, reduce_only)
        else:
            logger.warning("未启用自动降级，订单失败")
            return None
    
    def open_long(self, amount: float, df: pd.DataFrame = None, strategy: str = "", reason: str = "",
                  signal_strength: float = 1.0, volatility: float = 0.03) -> bool:
        """开多仓（P1优化：记录完整的交易信息）

        Args:
            amount: 开仓数量
            df: K线数据
            strategy: 策略名称
            reason: 开仓原因
            signal_strength: 信号强度 (0-1)
            volatility: 波动率 (百分比)
        """
        order = self.create_smart_order("buy", amount, signal_strength=signal_strength, volatility=volatility)

        if order:
            # 获取成交价格
            ticker = self.get_ticker()
            entry_price = ticker['last'] if ticker else 0

            # P1优化：获取订单详情以记录实际成交信息
            order_id = order.get('id', '')
            filled_price = entry_price  # 默认使用ticker价格
            filled_time = None
            fee = None
            fee_currency = None

            try:
                # 尝试获取订单详情
                if order_id and self.exchange:
                    order_detail = self.exchange.fetch_order(order_id, config.SYMBOL)
                    # 实际成交均价
                    filled_price = order_detail.get('average') or order_detail.get('price') or entry_price
                    # 实际成交时间
                    filled_time = order_detail.get('timestamp')
                    # 手续费信息
                    fee_info = order_detail.get('fee', {})
                    fee = fee_info.get('cost')
                    fee_currency = fee_info.get('currency')
            except Exception as e:
                logger.warning(f"获取订单详情失败: {e}，使用默认值")

            # 设置持仓
            self.risk_manager.set_position(
                side='long',
                amount=amount,
                entry_price=filled_price,  # 使用实际成交价
                df=df,
                strategy=strategy  # 传递策略名称用于差异化止损
            )

            # 记录到数据库（P1优化：包含完整的交易信息）
            db.log_trade_buffered(
                symbol=config.SYMBOL,
                side='long',
                action='open',
                amount=amount,
                price=entry_price,
                strategy=strategy or 'unknown',  # 使用传入的策略名称
                reason=reason,  # 记录开仓原因
                order_id=order_id,
                filled_price=filled_price,
                filled_time=filled_time,
                fee=fee,
                fee_currency=fee_currency
            )

            return True

        return False
    
    def open_short(self, amount: float, df: pd.DataFrame = None, strategy: str = "", reason: str = "",
                   signal_strength: float = 1.0, volatility: float = 0.03) -> bool:
        """开空仓（P1优化：记录完整的交易信息）

        Args:
            amount: 开仓数量
            df: K线数据
            strategy: 策略名称
            reason: 开仓原因
            signal_strength: 信号强度 (0-1)
            volatility: 波动率 (百分比)
        """
        order = self.create_smart_order("sell", amount, signal_strength=signal_strength, volatility=volatility)

        if order:
            ticker = self.get_ticker()
            entry_price = ticker['last'] if ticker else 0

            # P1优化：获取订单详情以记录实际成交信息
            order_id = order.get('id', '')
            filled_price = entry_price  # 默认使用ticker价格
            filled_time = None
            fee = None
            fee_currency = None

            try:
                # 尝试获取订单详情
                if order_id and self.exchange:
                    order_detail = self.exchange.fetch_order(order_id, config.SYMBOL)
                    # 实际成交均价
                    filled_price = order_detail.get('average') or order_detail.get('price') or entry_price
                    # 实际成交时间
                    filled_time = order_detail.get('timestamp')
                    # 手续费信息
                    fee_info = order_detail.get('fee', {})
                    fee = fee_info.get('cost')
                    fee_currency = fee_info.get('currency')
            except Exception as e:
                logger.warning(f"获取订单详情失败: {e}，使用默认值")

            self.risk_manager.set_position(
                side='short',
                amount=amount,
                entry_price=filled_price,  # 使用实际成交价
                df=df,
                strategy=strategy  # 传递策略名称用于差异化止损
            )

            # 记录到数据库（P1优化：包含完整的交易信息）
            db.log_trade_buffered(
                symbol=config.SYMBOL,
                side='short',
                action='open',
                amount=amount,
                price=entry_price,
                strategy=strategy or 'unknown',  # 使用传入的策略名称
                reason=reason,  # 记录开仓原因
                order_id=order_id,
                filled_price=filled_price,
                filled_time=filled_time,
                fee=fee,
                fee_currency=fee_currency
            )

            return True

        return False
    
    def close_position(self, reason: str = "", position_data: dict = None) -> bool:
        """
        平仓

        Args:
            reason: 平仓原因
            position_data: 可选的持仓数据字典（从get_positions()获取），如果不提供则使用risk_manager.position

        Returns:
            bool: 平仓是否成功
        """
        # 优先使用传入的持仓数据，否则使用风控管理器的持仓
        if position_data:
            # 使用传入的持仓数据（字典格式）
            position_side = position_data['side']
            position_amount = position_data['amount']
            position_entry_price = position_data['entry_price']
        elif self.risk_manager.position:
            # 使用风控管理器的持仓（对象格式）
            position_side = self.risk_manager.position.side
            position_amount = self.risk_manager.position.amount
            position_entry_price = self.risk_manager.position.entry_price
        else:
            # 如果都没有，尝试从交易所获取
            positions = self.get_positions()
            if not positions:
                logger.warning("无持仓可平")
                return False
            position_data = positions[0]
            position_side = position_data['side']
            position_amount = position_data['amount']
            position_entry_price = position_data['entry_price']

        # 修复：在平仓前先从数据库获取开仓记录的order_id
        opening_order_id = None
        try:
            conn = db._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT order_id FROM trades
                WHERE action = 'open'
                    AND side = ?
                    AND symbol = ?
                    AND NOT EXISTS (
                        SELECT 1 FROM trades t2
                        WHERE t2.order_id = trades.order_id AND t2.action = 'close'
                    )
                ORDER BY created_at DESC
                LIMIT 1
            """, (position_side, config.SYMBOL))
            result = cursor.fetchone()
            if result:
                opening_order_id = result[0]
                logger.debug(f"找到开仓order_id: {opening_order_id}")
            conn.close()
        except Exception as e:
            logger.warning(f"获取开仓order_id失败: {e}")

        # 使用 Bitget 一键平仓 API（双向持仓模式）
        try:
            result = self.exchange.private_mix_post_v2_mix_order_close_positions({
                'symbol': config.SYMBOL,
                'productType': config.PRODUCT_TYPE,
                'holdSide': position_side
            })

            if result.get('code') == '00000':
                order = result
                logger.info(f"一键平仓成功: {position_side}")
            else:
                logger.error(f"一键平仓失败: {result}")
                return False

        except Exception as e:
            logger.error(f"一键平仓API调用失败: {e}")
            # 回退到传统方法
            close_side = "sell" if position_side == 'long' else "buy"
            order = self.create_market_order(
                close_side,
                position_amount,
                reduce_only=True
            )

        if order:
            ticker = self.get_ticker()
            close_price = ticker['last'] if ticker else 0

            # 修复：优先使用开仓时的order_id，确保能正确关联开仓和平仓记录
            order_id = opening_order_id

            # 如果没有找到开仓order_id，尝试从订单中获取
            if not order_id:
                order_id = order.get('id', '') if isinstance(order, dict) else ''
                logger.warning(f"未找到开仓order_id，使用平仓订单ID: {order_id}")

            # 如果还是没有order_id，生成一个唯一标识符
            if not order_id:
                import uuid
                order_id = f"close_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
                logger.warning(f"无法获取order_id，生成临时ID: {order_id}")

            filled_price = close_price  # 默认使用ticker价格
            filled_time = None
            fee = None
            fee_currency = None

            try:
                # 尝试获取订单详情（仅当有真实order_id时，不是生成的临时ID）
                if order_id and not order_id.startswith('close_') and self.exchange:
                    order_detail = self.exchange.fetch_order(order_id, config.SYMBOL)
                    # 实际成交均价
                    filled_price = order_detail.get('average') or order_detail.get('price') or close_price
                    # 实际成交时间
                    filled_time = order_detail.get('timestamp')
                    # 手续费信息
                    fee_info = order_detail.get('fee', {})
                    fee = fee_info.get('cost')
                    fee_currency = fee_info.get('currency')
            except Exception as e:
                logger.warning(f"获取平仓订单详情失败: {e}，使用默认值")

            # 计算盈亏（使用实际成交价）
            if position_side == 'long':
                pnl = (filled_price - position_entry_price) * position_amount
            else:
                pnl = (position_entry_price - filled_price) * position_amount

            # 计算盈亏百分比
            pnl_percent = (pnl / (position_entry_price * position_amount)) * 100 * config.LEVERAGE

            # 记录交易结果
            self.risk_manager.record_trade_result(pnl)

            # 记录到数据库（修复：确保使用正确的order_id）
            db.log_trade_buffered(
                symbol=config.SYMBOL,
                side=position_side,
                action='close',
                amount=position_amount,
                price=close_price,
                pnl=pnl,
                pnl_percent=pnl_percent,
                reason=reason,
                order_id=order_id,  # 使用开仓时的order_id
                filled_price=filled_price,
                filled_time=filled_time,
                fee=fee,
                fee_currency=fee_currency
            )

            logger.info(f"✅ 平仓记录已写入数据库: order_id={order_id}, pnl={pnl:.4f}")
            
            # 清除持仓
            self.risk_manager.clear_position()
            
            logger.info(f"平仓成功: {reason}, PnL={pnl:.2f}")
            
            return True
        
        return False
    
    def partial_close(self, ratio: float, reason: str = "") -> bool:
        """部分平仓"""
        position = self.risk_manager.position
        if not position:
            return False
        
        close_amount = position.amount * ratio
        close_side = "sell" if position.side == 'long' else "buy"
        
        order = self.create_market_order(
            close_side,
            close_amount,
            reduce_only=True
        )
        
        if order:
            ticker = self.get_ticker()
            close_price = ticker['last'] if ticker else 0
            
            # 计算这部分的盈亏
            if position.side == 'long':
                pnl = (close_price - position.entry_price) * close_amount
            else:
                pnl = (position.entry_price - close_price) * close_amount
            
            # 更新持仓
            self.risk_manager.partial_close(ratio, close_price, pnl)
            
            db.log_trade_buffered(
                symbol=config.SYMBOL,
                side=position.side,
                action='partial_close',
                amount=close_amount,
                price=close_price,
                pnl=pnl,
                reason=reason
            )
            
            logger.info(f"部分平仓 {ratio:.0%}: {reason}, PnL={pnl:.2f}")
            
            return True
        
        return False
    
    def add_position(self, amount: float) -> bool:
        """加仓"""
        position = self.risk_manager.position
        if not position:
            return False
        
        can_add, reason = self.risk_manager.can_add_position(
            self.get_ticker()['last']
        )
        
        if not can_add:
            logger.info(f"不满足加仓条件: {reason}")
            return False
        
        add_side = "buy" if position.side == 'long' else "sell"
        order = self.create_market_order(add_side, amount)
        
        if order:
            ticker = self.get_ticker()
            add_price = ticker['last'] if ticker else 0
            
            self.risk_manager.add_position(amount, add_price)
            
            db.log_trade_buffered(
                symbol=config.SYMBOL,
                side=position.side,
                action='add',
                amount=amount,
                price=add_price
            )
            
            return True
        
        return False
    
    # ==================== 策略执行 ====================
    
    def run_strategy(self, df: pd.DataFrame) -> Optional[TradeSignal]:
        """运行策略分析"""
        if df is None or len(df) < 50:
            return None
        
        # 获取多时间周期数据
        if config.MULTI_TIMEFRAME_ENABLED:
            self.fetch_multi_timeframe_data()
        
        # 检查市场状态
        ind = IndicatorCalculator(df)
        market_state = ind.market_state()
        logger.debug(f"市场状态: {market_state['state']}, "
                    f"ADX={market_state['adx']:.1f}")
        
        # 选择合适的策略
        if "grid" in config.ENABLE_STRATEGIES and market_state['state'] == 'ranging':
            # 震荡市场用网格策略
            strategies_to_use = ["grid"]
        elif market_state['state'] in ['trending_up', 'trending_down']:
            # 趋势市场用趋势策略
            strategies_to_use = [s for s in config.ENABLE_STRATEGIES 
                               if s in ['macd_cross', 'ema_cross', 'adx_trend']]
        else:
            strategies_to_use = config.ENABLE_STRATEGIES
        
        if not strategies_to_use:
            strategies_to_use = config.ENABLE_STRATEGIES
        
        # 使用共识信号或单策略信号
        if config.USE_CONSENSUS_SIGNAL and len(strategies_to_use) > 1:
            signal = get_consensus_signal(
                df, 
                strategies_to_use,
                min_agreement=config.MIN_STRATEGY_AGREEMENT
            )
        else:
            signals = analyze_all_strategies(
                df, 
                strategies_to_use,
                min_strength=config.MIN_SIGNAL_STRENGTH,
                min_confidence=config.MIN_SIGNAL_CONFIDENCE
            )
            signal = signals[0] if signals else None
        
        if signal:
            logger.info(f"策略信号: {signal.signal.value} from {signal.strategy_name}")
            logger.info(f"  理由: {signal.reason}")
            logger.info(f"  强度: {signal.strength:.2f}, 置信度: {signal.confidence:.2f}")
        
        return signal
    
    def execute_signal(self, signal: TradeSignal, df: pd.DataFrame) -> bool:
        """执行交易信号"""
        if signal is None:
            return False
        
        # 检查是否可以交易
        can_trade, reason = self.risk_manager.can_open_position()
        if not can_trade and signal.signal in [Signal.LONG, Signal.SHORT]:
            logger.info(f"无法开仓: {reason}")
            return False
        
        # 检查回撤控制
        dd_can_trade, dd_reason = self.drawdown_controller.can_trade()
        if not dd_can_trade:
            logger.warning(f"回撤控制阻止交易: {dd_reason}")
            return False
        
        # 获取余额和价格
        balance = self.get_balance()
        ticker = self.get_ticker()
        if not ticker:
            return False
        
        current_price = ticker['last']
        
        # 执行信号
        if signal.signal == Signal.LONG:
            amount = self.risk_manager.calculate_position_size(
                balance, 
                current_price, 
                df,
                signal_strength=signal.strength
            )
            
            if amount > 0:
                if config.USE_PARTIAL_POSITION:
                    return self._execute_partial_open('long', amount, df)
                else:
                    return self.open_long(amount, df)
        
        elif signal.signal == Signal.SHORT:
            amount = self.risk_manager.calculate_position_size(
                balance, 
                current_price, 
                df,
                signal_strength=signal.strength
            )
            
            if amount > 0:
                if config.USE_PARTIAL_POSITION:
                    return self._execute_partial_open('short', amount, df)
                else:
                    return self.open_short(amount, df)
        
        elif signal.signal == Signal.CLOSE_LONG:
            if self.risk_manager.position and self.risk_manager.position.side == 'long':
                return self.close_position(signal.reason)
        
        elif signal.signal == Signal.CLOSE_SHORT:
            if self.risk_manager.position and self.risk_manager.position.side == 'short':
                return self.close_position(signal.reason)
        
        return False
    
    def _execute_partial_open(
        self, 
        side: str, 
        total_amount: float, 
        df: pd.DataFrame
    ) -> bool:
        """分批建仓"""
        self.position_builder = PositionBuilder(
            total_amount=total_amount,
            parts=config.POSITION_PARTS,
            entry_type=config.POSITION_ENTRY_TYPE
        )
        
        # 执行第一批
        first_amount = self.position_builder.get_next_amount()
        if first_amount is None:
            return False
        
        if side == 'long':
            success = self.open_long(first_amount, df)
        else:
            success = self.open_short(first_amount, df)
        
        if success:
            ticker = self.get_ticker()
            self.position_builder.record_entry(
                first_amount, 
                ticker['last'] if ticker else 0
            )
            logger.info(f"分批建仓 1/{config.POSITION_PARTS}: {first_amount:.6f}")
        
        return success
    
    def check_partial_entry(self, df: pd.DataFrame) -> bool:
        """检查是否需要继续建仓"""
        if self.position_builder is None or self.position_builder.is_complete():
            return False
        
        if self.risk_manager.position is None:
            return False
        
        # 检查是否满足加仓条件
        ticker = self.get_ticker()
        if not ticker:
            return False
        
        current_price = ticker['last']
        position = self.risk_manager.position
        
        # 盈利时才继续建仓
        is_profitable = (
            (position.side == 'long' and current_price > position.entry_price) or
            (position.side == 'short' and current_price < position.entry_price)
        )
        
        if not is_profitable:
            return False
        
        # 检查价格距离（至少变动一定比例才加仓）
        price_change = abs(current_price - position.entry_price) / position.entry_price
        if price_change < 0.003:  # 0.3%
            return False
        
        # 执行下一批建仓
        next_amount = self.position_builder.get_next_amount()
        if next_amount is None:
            return False
        
        success = self.add_position(next_amount)
        
        if success:
            self.position_builder.record_entry(next_amount, current_price)
            logger.info(f"分批建仓 {self.position_builder.current_part}/"
                       f"{config.POSITION_PARTS}: {next_amount:.6f}")
        
        return success
    
    # ==================== 止损止盈检查 ====================
    
    def check_stop_loss(self, df: pd.DataFrame) -> bool:
        """检查止损止盈"""
        position = self.risk_manager.position
        if not position:
            return False
        
        ticker = self.get_ticker()
        if not ticker:
            return False
        
        current_price = ticker['last']
        
        # 检查止损
        stop_result = self.risk_manager.check_stop_loss(
            current_price, 
            position, 
            df
        )
        
        if stop_result.should_stop:
            logger.warning(f"触发{stop_result.stop_type}: {stop_result.reason}")
            
            # 分批止盈
            if stop_result.stop_type == "take_profit" and config.USE_PARTIAL_TAKE_PROFIT:
                return self._execute_partial_take_profit(current_price)
            else:
                return self.close_position(stop_result.reason)
        
        # 检查策略退出信号
        for strategy_name in config.ENABLE_STRATEGIES:
            try:
                strategy = get_strategy(strategy_name, df)
                exit_signal = strategy.check_exit(position.side)

                if exit_signal.signal in [Signal.CLOSE_LONG, Signal.CLOSE_SHORT]:
                    logger.info(f"策略退出信号: {exit_signal.reason}")
                    return self.close_position(exit_signal.reason)
            except Exception as e:
                logger.debug(f"检查策略 {strategy_name} 退出信号失败: {e}")
                pass
        
        return False
    
    def _execute_partial_take_profit(self, current_price: float) -> bool:
        """分批止盈"""
        position = self.risk_manager.position
        if not position:
            return False
        
        # 初始化分批平仓器
        if self.position_closer is None:
            self.position_closer = PositionCloser(position.amount)
            
            # 设置多个止盈目标
            entry = position.entry_price
            if position.side == 'long':
                self.position_closer.add_target(
                    entry * (1 + config.TAKE_PROFIT_PERCENT * 0.5), 0.3
                )
                self.position_closer.add_target(
                    entry * (1 + config.TAKE_PROFIT_PERCENT * 0.8), 0.3
                )
                self.position_closer.add_target(
                    entry * (1 + config.TAKE_PROFIT_PERCENT * 1.2), 0.4
                )
            else:
                self.position_closer.add_target(
                    entry * (1 - config.TAKE_PROFIT_PERCENT * 0.5), 0.3
                )
                self.position_closer.add_target(
                    entry * (1 - config.TAKE_PROFIT_PERCENT * 0.8), 0.3
                )
                self.position_closer.add_target(
                    entry * (1 - config.TAKE_PROFIT_PERCENT * 1.2), 0.4
                )
        
        # 检查并执行分批平仓
        close_amount = self.position_closer.check_targets(current_price, position.side)
        
        if close_amount and close_amount > 0:
            ratio = close_amount / position.amount
            return self.partial_close(ratio, "分批止盈")
        
        return False
    
    # ==================== 主循环 ====================
    
    def run_once(self) -> Dict:
        """执行一次完整的交易循环"""
        result = {
            'success': False,
            'action': None,
            'signal': None,
            'error': None,
        }
        
        try:
            # 健康检查
            if self.health_monitor.should_reconnect():
                self.reconnect()
            
            self.health_monitor.update_heartbeat()
            
            # 同步持仓
            self.sync_position()
            
            # 获取K线数据
            df = self.fetch_ohlcv()
            if df is None:
                result['error'] = "获取K线失败"
                return result
            
            # 更新权益
            balance = self.get_balance()
            if balance > 0:
                self.risk_manager.update_equity(balance)
                self.drawdown_controller.update(balance)
            
            # 有持仓时检查止损
            if self.risk_manager.position:
                if self.check_stop_loss(df):
                    result['action'] = 'stop_loss'
                    result['success'] = True
                    return result
                
                # 检查分批建仓
                if self.check_partial_entry(df):
                    result['action'] = 'partial_entry'
                    result['success'] = True
                    return result
                
                # 检查分批止盈
                ticker = self.get_ticker()
                if ticker:
                    self._execute_partial_take_profit(ticker['last'])
            
            # 无持仓时检查开仓信号
            else:
                signal = self.run_strategy(df)
                result['signal'] = signal
                
                if signal and signal.signal in [Signal.LONG, Signal.SHORT]:
                    if self.execute_signal(signal, df):
                        result['action'] = 'open_position'
                        result['success'] = True
            
            return result
            
        except Exception as e:
            logger.error(f"交易循环错误: {e}")
            result['error'] = str(e)
            return result
    
    def run(self):
        """主循环"""
        logger.info("=" * 50)
        logger.info("交易机器人启动")
        logger.info(f"交易对: {config.SYMBOL}")
        logger.info(f"时间周期: {config.TIMEFRAME}")
        logger.info(f"策略: {config.ENABLE_STRATEGIES}")
        logger.info(f"杠杆: {config.LEVERAGE}x")
        logger.info("=" * 50)
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                logger.debug(f"--- 循环 #{cycle_count} ---")
                
                result = self.run_once()
                
                if result['action']:
                    logger.info(f"执行动作: {result['action']}")
                
                if result['error']:
                    logger.error(f"循环错误: {result['error']}")
                
                # 打印状态
                if cycle_count % 10 == 0:
                    self._print_status()
                
                
                # 刷新数据库缓冲区
                try:
                    db.flush_buffers()
                except Exception as e:
                    logger.error(f"刷新数据库缓冲区失败: {e}")
                # 等待下一个周期
                time.sleep(config.CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("收到退出信号，正在关闭...")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                time.sleep(config.API_ERROR_COOLDOWN)
        
        
        # 强制刷新数据库缓冲区
        try:
            db.flush_buffers(force=True)
            logger.info("✅ 数据库缓冲区已刷新")
        except Exception as e:
            logger.error(f"刷新数据库缓冲区失败: {e}")
        logger.info("交易机器人已关闭")
    
    def _print_status(self):
        """打印状态信息"""
        position = self.risk_manager.position
        metrics = self.risk_manager.metrics
        
        logger.info("=" * 40)
        logger.info(f"余额: {self.get_balance():.2f} USDT")
        
        if position:
            logger.info(f"持仓: {position.side} {position.amount:.6f}")
            logger.info(f"开仓价: {position.entry_price:.2f}")
            logger.info(f"未实现盈亏: {position.unrealized_pnl:.2f} "
                       f"({position.unrealized_pnl_pct:.2f}%)")
            logger.info(f"止损价: {position.stop_loss_price:.2f}")
        else:
            logger.info("无持仓")
        
        logger.info(f"胜率: {metrics.win_rate:.1%}")
        logger.info(f"连续亏损: {metrics.consecutive_losses}")
        logger.info(f"回撤: {metrics.current_drawdown:.1%}")
        logger.info("=" * 40)
    
    def get_status(self) -> Dict:
        """获取完整状态"""
        return {
            'position': {
                'side': self.risk_manager.position.side if self.risk_manager.position else None,
                'amount': self.risk_manager.position.amount if self.risk_manager.position else 0,
                'entry_price': self.risk_manager.position.entry_price if self.risk_manager.position else 0,
                'unrealized_pnl': self.risk_manager.position.unrealized_pnl if self.risk_manager.position else 0,
            },
            'risk': self.risk_manager.get_risk_report(),
            'health': {
                'is_healthy': self.health_monitor.is_healthy,
                'api_errors': self.health_monitor.api_errors,
                'reconnect_count': self.health_monitor.reconnect_count,
            },
            'drawdown': {
                'is_locked': self.drawdown_controller.is_locked,
                'lock_reason': self.drawdown_controller.lock_reason,
            },
        }


# ==================== 入口 ====================

def main():
    """主函数"""
    trader = BitgetTrader()
    trader.run()


if __name__ == "__main__":
    main()

