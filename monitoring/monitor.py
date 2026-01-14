"""
监控脚本 - 定期检查机器人状态
"""
import time
import sys
from datetime import datetime, timedelta

from config.settings import settings as config
from core.trader import BitgetTrader
from utils.logger_utils import db, notifier, get_logger

logger = get_logger("monitor")


class BotMonitor:
    """机器人监控器"""
    
    def __init__(self):
        self.trader = BitgetTrader()
        self.last_trade_check = datetime.now()
        self.alert_cooldown = {}  # 警报冷却
    
    def check_health(self) -> dict:
        """健康检查"""
        status = {
            'healthy': True,
            'issues': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # 检查 API 连接
            balance = self.trader.get_balance()
            if balance is None:
                status['healthy'] = False
                status['issues'].append("API 连接失败")
            else:
                status['balance'] = balance
            
            # 检查持仓同步
            self.trader.sync_position()
            position = self.trader.risk_manager.position
            
            if position:
                status['position'] = {
                    'side': position.side,
                    'amount': position.amount,
                    'entry_price': position.entry_price,
                    'unrealized_pnl': position.unrealized_pnl,
                    'unrealized_pnl_pct': position.unrealized_pnl_pct,
                }
                
                # 检查浮亏是否过大
                if position.unrealized_pnl_pct < -config.STOP_LOSS_PERCENT * 100 * 1.5:
                    status['issues'].append(f"浮亏过大: {position.unrealized_pnl_pct:.2f}%")
            
            # 检查回撤
            metrics = self.trader.risk_manager.metrics
            if metrics.current_drawdown > config.STOP_LOSS_PERCENT * 2:
                status['issues'].append(f"回撤警告: {metrics.current_drawdown:.1%}")
            
            status['metrics'] = {
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'consecutive_losses': metrics.consecutive_losses,
                'current_drawdown': metrics.current_drawdown,
            }
            
        except Exception as e:
            status['healthy'] = False
            status['issues'].append(f"检查异常: {str(e)}")
        
        return status
    
    def check_recent_activity(self, hours: int = 24) -> dict:
        """检查最近活动"""
        trades = db.get_trades(limit=100)
        
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_trades = []
        
        for trade in trades:
            try:
                trade_time = datetime.fromisoformat(trade['created_at'])
                if trade_time > cutoff:
                    recent_trades.append(trade)
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"跳过无效交易记录: {e}")
                pass
        
        total_pnl = sum(t.get('pnl', 0) for t in recent_trades)
        winning = len([t for t in recent_trades if t.get('pnl', 0) > 0])
        losing = len([t for t in recent_trades if t.get('pnl', 0) < 0])
        
        return {
            'period_hours': hours,
            'total_trades': len(recent_trades),
            'winning_trades': winning,
            'losing_trades': losing,
            'total_pnl': total_pnl,
            'trades': recent_trades[:10],  # 最近10笔
        }
    
    def send_alert(self, alert_type: str, message: str, cooldown_minutes: int = 30):
        """发送警报（带冷却）"""
        now = datetime.now()
        
        # 检查冷却
        if alert_type in self.alert_cooldown:
            if now < self.alert_cooldown[alert_type]:
                return False
        
        # 设置冷却
        self.alert_cooldown[alert_type] = now + timedelta(minutes=cooldown_minutes)
        
        # 发送通知
        logger.warning(f"[{alert_type}] {message}")
        notifier.send_message(f"⚠️ <b>{alert_type}</b>\n{message}")
        
        return True
    
    def generate_daily_report(self) -> str:
        """生成每日报告"""
        stats = db.get_statistics(days=1)
        activity = self.check_recent_activity(hours=24)
        health = self.check_health()
        
        report = []
        report.append("=" * 50)
        report.append(f"每日报告 - {datetime.now().strftime('%Y-%m-%d')}")
        report.append("=" * 50)
        
        # 账户状态
        report.append(f"\n【账户状态】")
        report.append(f"余额: {health.get('balance', 'N/A')} USDT")
        
        if health.get('position'):
            pos = health['position']
            report.append(f"持仓: {pos['side']} {pos['amount']:.6f}")
            report.append(f"浮盈: {pos['unrealized_pnl']:.2f} USDT ({pos['unrealized_pnl_pct']:.2f}%)")
        else:
            report.append("持仓: 无")
        
        # 交易统计
        report.append(f"\n【24小时交易】")
        report.append(f"交易次数: {activity['total_trades']}")
        report.append(f"盈利: {activity['winning_trades']} 笔")
        report.append(f"亏损: {activity['losing_trades']} 笔")
        report.append(f"总盈亏: {activity['total_pnl']:+.2f} USDT")
        
        # 风险指标
        if health.get('metrics'):
            metrics = health['metrics']
            report.append(f"\n【风险指标】")
            report.append(f"总交易: {metrics['total_trades']}")
            report.append(f"胜率: {metrics['win_rate']:.1%}")
            report.append(f"连续亏损: {metrics['consecutive_losses']}")
            report.append(f"当前回撤: {metrics['current_drawdown']:.1%}")
        
        # 问题警告
        if health.get('issues'):
            report.append(f"\n【警告】")
            for issue in health['issues']:
                report.append(f"⚠️ {issue}")
        
        report.append("\n" + "=" * 50)
        
        return "\n".join(report)
    
    def run(self, interval: int = 300):
        """运行监控循环"""
        logger.info("监控服务启动")
        
        last_daily_report = None
        
        while True:
            try:
                # 健康检查
                health = self.check_health()
                
                if not health['healthy']:
                    for issue in health['issues']:
                        self.send_alert("健康检查", issue)
                
                # 每日报告（每天早上9点）
                now = datetime.now()
                if now.hour == 9 and last_daily_report != now.date():
                    report = self.generate_daily_report()
                    print(report)
                    notifier.send_message(f"<pre>{report}</pre>")
                    last_daily_report = now.date()
                
                # 打印状态
                logger.info(f"监控检查完成 - 余额: {health.get('balance', 'N/A')} USDT")
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("监控服务停止")
                break
            except Exception as e:
                logger.error(f"监控异常: {e}")
                time.sleep(60)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='交易机器人监控')
    parser.add_argument('--check', action='store_true', help='单次健康检查')
    parser.add_argument('--report', action='store_true', help='生成报告')
    parser.add_argument('--interval', type=int, default=300, help='监控间隔（秒）')
    
    args = parser.parse_args()
    
    monitor = BotMonitor()
    
    if args.check:
        health = monitor.check_health()
        print(f"健康状态: {'✅ 正常' if health['healthy'] else '❌ 异常'}")
        if health.get('balance'):
            print(f"余额: {health['balance']} USDT")
        if health.get('issues'):
            print("问题:")
            for issue in health['issues']:
                print(f"  - {issue}")
    
    elif args.report:
        report = monitor.generate_daily_report()
        print(report)
    
    else:
        monitor.run(interval=args.interval)


if __name__ == "__main__":
    main()
