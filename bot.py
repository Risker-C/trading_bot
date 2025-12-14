import time
import signal
import sys
from datetime import datetime
from typing import Optional

import config
from trader import BitgetTrader
from risk_manager import RiskManager
from strategies import (
    Signal, TradeSignal,
    get_strategy, analyze_all_strategies, STRATEGY_MAP
)
from market_regime import MarketRegimeDetector
from logger_utils import get_logger, db, notifier

logger = get_logger("bot")


class TradingBot:
    """量化交易机器人"""
    
    def __init__(self):
        self.trader = BitgetTrader()
        self.risk_manager = RiskManager(self.trader)
        self.running = False
        self.current_position_side: Optional[str] = None
        self.current_strategy: Optional[str] = None
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info("收到退出信号，正在停止...")
        self.running = False
    
    def start(self):
        """启动机器人"""
        logger.info("=" * 50)
        logger.info("🤖 量化交易机器人启动")
        logger.info("=" * 50)

        # 检查交易所连接
        if self.trader.exchange is None:
            logger.error("交易所初始化失败，退出")
            return

        # 显示配置
        self._show_config()
        
        # 显示账户信息
        self._show_account_info()
        
        # 检查现有持仓
        self._check_existing_positions()
        
        # 主循环
        self.running = True
        logger.info(f"开始监控，检查间隔: {config.CHECK_INTERVAL} 秒")
        
        while self.running:
            try:
                self._main_loop()
            except Exception as e:
                logger.error(f"主循环异常: {e}")
                notifier.notify_error(str(e))
            
            # 等待下一次检查
            if self.running:
                time.sleep(config.CHECK_INTERVAL)
        
        logger.info("机器人已停止")
    
    def _show_config(self):
        """显示配置信息"""
        logger.info("\n📋 当前配置:")
        logger.info(f"   交易对: {config.SYMBOL}")
        logger.info(f"   杠杆: {config.LEVERAGE}x")
        logger.info(f"   保证金模式: {config.MARGIN_MODE}")
        logger.info(f"   仓位比例: {config.POSITION_SIZE_PERCENT:.0%}")
        logger.info(f"   止损: {config.STOP_LOSS_PERCENT:.0%}")
        logger.info(f"   止盈: {config.TAKE_PROFIT_PERCENT:.0%}")
        logger.info(f"   移动止损: {config.TRAILING_STOP_PERCENT:.0%}")
        logger.info(f"   K线周期: {config.TIMEFRAME}")
        logger.info(f"   启用策略: {', '.join(config.ENABLE_STRATEGIES)}")
    
    def _show_account_info(self):
        """显示账户信息"""
        balance = self.trader.get_balance()
        logger.info("\n💰 账户余额:")
        logger.info(f"   可用: {balance:.2f} USDT")

        # 记录余额快照
        db.log_balance_snapshot(balance, balance, 0)
    
    def _check_existing_positions(self):
        """检查现有持仓"""
        positions = self.trader.get_positions()
        
        if positions:
            logger.info("\n📊 现有持仓:")
            for pos in positions:
                logger.info(f"   {pos.side.upper()}: {pos.amount} @ {pos.entry_price:.2f}")
                logger.info(f"   未实现盈亏: {pos.unrealized_pnl:.2f} USDT ({pos.pnl_percent:.2f}%)")
                
                # 初始化风控状态
                self.current_position_side = pos.side
                self.risk_manager.on_position_opened(
                    pos.side, 
                    pos.amount, 
                    pos.entry_price
                )
                
                # 记录持仓快照
                db.log_position_snapshot(
                    pos.symbol, pos.side, pos.amount,
                    pos.entry_price, pos.current_price,
                    pos.unrealized_pnl, pos.leverage
                )
        else:
            logger.info("\n📊 当前无持仓")
    
    def _main_loop(self):
        """主循环逻辑"""
        # 获取K线数据
        df = self.trader.get_klines()
        if df.empty:
            logger.warning("获取K线数据失败")
            return
        
        # 获取当前价格
        ticker = self.trader.get_ticker()
        if not ticker:
            logger.warning("获取行情失败")
            return
        
        current_price = ticker['last']
        
        # 获取当前持仓
        positions = self.trader.get_positions()
        has_position = len(positions) > 0
        
        if has_position:
            # 有持仓：检查风控和退出信号
            self._check_exit_conditions(df, current_price, positions[0])
        else:
            # 无持仓：检查开仓信号
            self._check_entry_conditions(df, current_price)
    
    def _check_entry_conditions(self, df, current_price: float):
        """检查开仓条件"""

        # 风控检查
        can_open, reason = self.risk_manager.can_open_position()
        if not can_open:
            logger.debug(f"风控限制: {reason}")
            return

        # 市场状态检测
        detector = MarketRegimeDetector(df)
        regime_info = detector.detect()

        # 检查是否适合交易
        can_trade, trade_reason = detector.should_trade(regime_info)
        if not can_trade:
            logger.debug(f"市场状态不适合交易: {trade_reason}")
            return

        # 根据市场状态动态选择策略
        if hasattr(config, 'USE_DYNAMIC_STRATEGY') and config.USE_DYNAMIC_STRATEGY:
            # 动态策略选择
            selected_strategies = detector.get_suitable_strategies(regime_info)
            logger.info(
                f"市场状态: {regime_info.regime.value.upper()} "
                f"(ADX={regime_info.adx:.1f}, 宽度={regime_info.bb_width:.2f}%) "
                f"→ 策略: {', '.join(selected_strategies)}"
            )
        else:
            # 使用配置文件中的固定策略
            selected_strategies = config.ENABLE_STRATEGIES

        # 运行选定的策略
        signals = analyze_all_strategies(df, selected_strategies)

        # 找到第一个有效的开仓信号
        for trade_signal in signals:
            if trade_signal.signal == Signal.LONG:
                self._execute_open_long(trade_signal, current_price)
                return
            elif trade_signal.signal == Signal.SHORT:
                self._execute_open_short(trade_signal, current_price)
                return

        # 无信号
        logger.debug(f"当前价格: {current_price:.2f} - 无开仓信号")
    
    def _check_exit_conditions(self, df, current_price: float, position):
        """检查退出条件"""
        
        # 1. 检查风控止损止盈
        should_close, reason = self.risk_manager.check_risk(current_price)
        if should_close:
            logger.warning(f"风控触发: {reason}")
            self._execute_close_position(position, reason, "risk")
            return
        
        # 2. 检查策略退出信号
        if self.current_strategy and self.current_strategy in STRATEGY_MAP:
            strategy = get_strategy(self.current_strategy, df)
            exit_signal = strategy.check_exit(position.side)
            
            if exit_signal.signal in [Signal.CLOSE_LONG, Signal.CLOSE_SHORT]:
                logger.info(f"策略退出信号: {exit_signal.reason}")
                self._execute_close_position(position, exit_signal.reason, "strategy")
                return
        
        # 3. 显示持仓状态
        pnl_pct = position.pnl_percent
        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
        
        logger.info(
            f"持仓中 | {position.side.upper()} | "
            f"入场: {position.entry_price:.2f} | "
            f"现价: {current_price:.2f} | "
            f"{pnl_emoji} {pnl_pct:+.2f}%"
        )
    
    def _execute_open_long(self, signal: TradeSignal, current_price: float):
        """执行开多"""
        logger.info(f"📈 开多信号 [{signal.strategy}]: {signal.reason}")
        
        # 记录信号
        db.log_signal(
            signal.strategy, signal.signal.value,
            signal.reason, signal.strength, signal.confidence, signal.indicators
        )
        
        # 执行开仓
        result = self.trader.open_long()
        
        if result.success:
            self.current_position_side = 'long'
            self.current_strategy = signal.strategy
            
            # 获取实际成交价格
            positions = self.trader.get_positions()
            entry_price = current_price
            if positions:
                entry_price = positions[0].entry_price
            
            # 初始化风控
            self.risk_manager.on_position_opened('long', result.amount, entry_price)
            
            # 记录交易
            db.log_trade(
                config.SYMBOL, 'long', 'open',
                result.amount, entry_price,
                order_id=result.order_id,
                value_usdt=result.amount * entry_price,
                strategy=signal.strategy, reason=signal.reason
            )
            
            # 发送通知
            notifier.notify_trade(
                'open', config.SYMBOL, 'long',
                result.amount, entry_price, reason=signal.reason
            )
            
            logger.info(f"✅ 开多成功: {result.amount} @ {entry_price:.2f}")
        else:
            logger.error(f"❌ 开多失败: {result.error}")
            notifier.notify_error(f"开多失败: {result.error}")
    
    def _execute_open_short(self, signal: TradeSignal, current_price: float):
        """执行开空"""
        logger.info(f"📉 开空信号 [{signal.strategy}]: {signal.reason}")
        
        # 记录信号
        db.log_signal(
            signal.strategy, signal.signal.value,
            signal.reason, signal.strength, signal.confidence, signal.indicators
        )
        
        # 执行开仓
        result = self.trader.open_short()
        
        if result.success:
            self.current_position_side = 'short'
            self.current_strategy = signal.strategy
            
            # 获取实际成交价格
            positions = self.trader.get_positions()
            entry_price = current_price
            if positions:
                entry_price = positions[0].entry_price
            
            # 初始化风控
            self.risk_manager.on_position_opened('short', result.amount, entry_price)
            
            # 记录交易
            db.log_trade(
                config.SYMBOL, 'short', 'open',
                result.amount, entry_price,
                order_id=result.order_id,
                value_usdt=result.amount * entry_price,
                strategy=signal.strategy, reason=signal.reason
            )
            
            # 发送通知
            notifier.notify_trade(
                'open', config.SYMBOL, 'short',
                result.amount, entry_price, reason=signal.reason
            )
            
            logger.info(f"✅ 开空成功: {result.amount} @ {entry_price:.2f}")
        else:
            logger.error(f"❌ 开空失败: {result.error}")
            notifier.notify_error(f"开空失败: {result.error}")
    
    def _execute_close_position(self, position, reason: str, trigger_type: str):
        """执行平仓"""
        logger.info(f"📤 平仓触发 [{trigger_type}]: {reason}")
        
        # 计算盈亏
        entry_price = position.entry_price
        current_price = position.current_price
        amount = position.amount
        
        if position.side == 'long':
            pnl = (current_price - entry_price) * amount
            result = self.trader.close_long(amount)
        else:
            pnl = (entry_price - current_price) * amount
            result = self.trader.close_short(amount)
        
        pnl_percent = position.pnl_percent
        
        if result.success:
            # 更新风控状态
            self.risk_manager.on_position_closed(pnl)
            
            # 重置当前持仓信息
            self.current_position_side = None
            self.current_strategy = None
            
            # 记录交易
            db.log_trade(
                config.SYMBOL, position.side, 'close',
                amount, current_price,
                order_id=result.order_id,
                value_usdt=amount * current_price,
                pnl=pnl, pnl_percent=pnl_percent,
                strategy=self.current_strategy or "", reason=reason
            )
            
            # 记录风控事件
            db.log_risk_event(
                trigger_type, reason,
                current_price, entry_price, position.side
            )
            
            # 发送通知
            notifier.notify_trade(
                'close', config.SYMBOL, position.side,
                amount, current_price, pnl=pnl, reason=reason
            )
            
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            logger.info(f"✅ 平仓成功: {amount} @ {current_price:.2f} | {pnl_emoji} {pnl:+.2f} USDT ({pnl_percent:+.2f}%)")
        else:
            logger.error(f"❌ 平仓失败: {result.error}")
            notifier.notify_error(f"平仓失败: {result.error}")
    
    def get_status(self) -> dict:
        """获取机器人状态"""
        balance = self.trader.get_balance()
        positions = self.trader.get_positions()
        risk_status = self.risk_manager.get_status()
        
        return {
            'running': self.running,
            'balance': balance,
            'positions': [
                {
                    'side': p.side,
                    'amount': p.amount,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'pnl': p.unrealized_pnl,
                    'pnl_percent': p.pnl_percent,
                }
                for p in positions
            ],
            'risk': risk_status,
            'current_strategy': self.current_strategy,
        }
    
    def stop(self):
        """停止机器人"""
        self.running = False
        logger.info("机器人停止中...")
    
    def close_all(self):
        """紧急平仓"""
        logger.warning("执行紧急平仓")
        results = self.trader.close_all_positions()
        
        for result in results:
            if result.success:
                logger.info(f"平仓成功: {result.order_id}")
            else:
                logger.error(f"平仓失败: {result.error}")
        
        return results


def main():
    """主函数"""
    bot = TradingBot()
    
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        notifier.notify_error(str(e))
    finally:
        logger.info("程序退出")


if __name__ == "__main__":
    main()
