"""
交易执行器 - 增强版
"""
import ccxt
import time
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import pandas as pd

import config
from logger_utils import get_logger, db
from strategies import (
    Signal, TradeSignal, get_strategy, analyze_all_strategies,
    get_consensus_signal, STRATEGY_MAP
)
from risk_manager import (
    RiskManager, PositionInfo, PositionBuilder, 
    PositionCloser, DrawdownController
)
from indicators import IndicatorCalculator

logger = get_logger("trader")


class HealthMonitor:
    """健康监控器"""
    
    def __init__(self):
        self.api_errors = 0
        self.last_heartbeat = datetime.now()
        self.last_successful_request = datetime.now()
        self.is_healthy = True
        self.reconnect_count = 0
    
    def record_success(self):
        """记录成功请求"""
        self.api_errors = 0
        self.last_successful_request = datetime.now()
        self.is_healthy = True
    
    def record_error(self, error: Exception):
        """记录错误"""
        self.api_errors += 1
        logger.error(f"API错误 ({self.api_errors}): {error}")
        
        if self.api_errors >= config.MAX_API_ERRORS:
            self.is_healthy = False
            logger.error(f"连续 {self.api_errors} 次错误，标记为不健康")
    
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


class BitgetTrader:
    """Bitget 交易执行器"""
    
    def __init__(self):
        self.exchange = None
        self.risk_manager = RiskManager(self)
        self.drawdown_controller = DrawdownController()
        self.health_monitor = HealthMonitor()
        
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
                "apiKey": config.EXCHANGE_CONFIG["apiKey"],
                "secret": config.EXCHANGE_CONFIG["secret"],
                "password": config.EXCHANGE_CONFIG["password"],
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
        """获取多时间周期数据"""
        if not config.MULTI_TIMEFRAME_ENABLED:
            return {}
        
        data = {}
        for tf in config.TIMEFRAMES:
            df = self.fetch_ohlcv(timeframe=tf)
            if df is not None:
                data[tf] = df
            time.sleep(0.5)  # 避免频率限制
        
        self.timeframe_data = data
        return data
    
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
    
    def open_long(self, amount: float, df: pd.DataFrame = None) -> bool:
        """开多仓"""
        order = self.create_market_order("buy", amount)
        
        if order:
            # 获取成交价格
            ticker = self.get_ticker()
            entry_price = ticker['last'] if ticker else 0
            
            # 设置持仓
            self.risk_manager.set_position(
                side='long',
                amount=amount,
                entry_price=entry_price,
                df=df
            )
            
            # 记录到数据库
            db.log_trade(
                symbol=config.SYMBOL,
                side='long',
                action='open',
                amount=amount,
                price=entry_price,
                strategy=order.get('info', {}).get('strategy', 'unknown')
            )
            
            return True
        
        return False
    
    def open_short(self, amount: float, df: pd.DataFrame = None) -> bool:
        """开空仓"""
        order = self.create_market_order("sell", amount)
        
        if order:
            ticker = self.get_ticker()
            entry_price = ticker['last'] if ticker else 0
            
            self.risk_manager.set_position(
                side='short',
                amount=amount,
                entry_price=entry_price,
                df=df
            )
            
            db.log_trade(
                symbol=config.SYMBOL,
                side='short',
                action='open',
                amount=amount,
                price=entry_price
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

            # 计算盈亏
            if position_side == 'long':
                pnl = (close_price - position_entry_price) * position_amount
            else:
                pnl = (position_entry_price - close_price) * position_amount

            # 记录交易结果
            self.risk_manager.record_trade_result(pnl)

            # 记录到数据库
            db.log_trade(
                symbol=config.SYMBOL,
                side=position_side,
                action='close',
                amount=position_amount,
                price=close_price,
                pnl=pnl,
                reason=reason
            )
            
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
            
            db.log_trade(
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
            
            db.log_trade(
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
                
                # 等待下一个周期
                time.sleep(config.CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("收到退出信号，正在关闭...")
                break
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                time.sleep(config.API_ERROR_COOLDOWN)
        
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

