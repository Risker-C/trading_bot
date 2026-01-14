"""
性能分析器
计算6个关键指标 + 分阶段拒绝贡献度
不只看胜率，全面评估系统质量
"""
import sqlite3
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from utils.logger_utils import get_logger, db

logger = get_logger("performance_analyzer")


class PerformanceAnalyzer:
    """性能分析器"""

    def __init__(self):
        pass  # Database connections are created per-method

    def analyze_period(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        strategy: Optional[str] = None
    ) -> Dict:
        """
        分析指定时期的性能

        Args:
            start_date: 开始日期
            end_date: 结束日期
            strategy: 策略名称（可选）

        Returns:
            完整的性能分析报告
        """
        logger.info(f"开始性能分析: {start_date} ~ {end_date}")

        report = {
            'period': {
                'start': start_date or 'all',
                'end': end_date or 'all',
                'strategy': strategy or 'all'
            },
            'core_metrics': self._calculate_core_metrics(start_date, end_date, strategy),
            'rejection_analysis': self._analyze_rejections(start_date, end_date, strategy),
            'claude_analysis': self._analyze_claude_performance(start_date, end_date, strategy),
            'execution_quality': self._analyze_execution_quality(start_date, end_date, strategy),
            'risk_analysis': self._analyze_risk_metrics(start_date, end_date, strategy),
        }

        return report

    def _calculate_core_metrics(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        strategy: Optional[str]
    ) -> Dict:
        """
        计算6个核心指标：
        1. Max Drawdown（最大回撤）
        2. Loss Streak P95（95分位连续亏损）
        3. Profit Factor（盈亏比）
        4. Expectancy per Trade（单笔期望）
        5. Avg Slippage per Trade（平均滑点）
        6. Win Rate（胜率，作为参考）
        """
        query = """
            SELECT
                pnl,
                pnl_pct,
                entry_price,
                exit_price,
                timestamp,
                exit_time
            FROM trade_tags
            WHERE executed = 1 AND pnl != 0
        """
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        query += " ORDER BY timestamp"

        conn = db._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        trades = cursor.fetchall()
        conn.close()

        if not trades:
            return {
                'total_trades': 0,
                'error': 'No trades found'
            }

        # 提取数据
        pnls = [t['pnl'] for t in trades]
        pnl_pcts = [t['pnl_pct'] for t in trades]

        # 1. Max Drawdown
        cumulative_pnl = []
        running_sum = 0
        for pnl in pnls:
            running_sum += pnl
            cumulative_pnl.append(running_sum)

        peak = cumulative_pnl[0]
        max_drawdown = 0
        for value in cumulative_pnl:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        max_drawdown_pct = (max_drawdown / abs(peak)) * 100 if peak != 0 else 0

        # 2. Loss Streak P95
        loss_streaks = []
        current_streak = 0
        for pnl in pnls:
            if pnl < 0:
                current_streak += 1
            else:
                if current_streak > 0:
                    loss_streaks.append(current_streak)
                current_streak = 0

        if current_streak > 0:
            loss_streaks.append(current_streak)

        if loss_streaks:
            loss_streaks.sort()
            p95_index = int(len(loss_streaks) * 0.95)
            loss_streak_p95 = loss_streaks[p95_index] if p95_index < len(loss_streaks) else loss_streaks[-1]
            max_loss_streak = max(loss_streaks)
        else:
            loss_streak_p95 = 0
            max_loss_streak = 0

        # 3. Profit Factor
        total_profit = sum(p for p in pnls if p > 0)
        total_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # 4. Expectancy per Trade
        expectancy = sum(pnls) / len(pnls)

        # 5. Avg Slippage per Trade
        # 假设滑点 = |实际成交价 - 预期价格| / 预期价格
        # 这里简化为 0，因为我们没有记录预期价格
        # 实际应该在执行时记录
        avg_slippage = 0.0  # TODO: 需要在trade_tags中添加expected_price字段

        # 6. Win Rate
        winning_trades = sum(1 for p in pnls if p > 0)
        win_rate = winning_trades / len(pnls)

        # 额外指标
        avg_win = total_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = total_loss / (len(pnls) - winning_trades) if (len(pnls) - winning_trades) > 0 else 0

        return {
            'total_trades': len(trades),
            'winning_trades': winning_trades,
            'losing_trades': len(pnls) - winning_trades,

            # 核心指标
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'loss_streak_p95': loss_streak_p95,
            'max_loss_streak': max_loss_streak,
            'profit_factor': profit_factor,
            'expectancy_per_trade': expectancy,
            'avg_slippage_per_trade': avg_slippage,
            'win_rate': win_rate,

            # 额外指标
            'total_pnl': sum(pnls),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_pnl_pct': sum(pnl_pcts) / len(pnl_pcts),
        }

    def _analyze_rejections(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        strategy: Optional[str]
    ) -> Dict:
        """
        分析拒绝率分布
        各阶段拒绝了多少信号
        """
        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN trend_filter_pass = 0 THEN 1 ELSE 0 END) as rejected_by_trend,
                SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 0 THEN 1 ELSE 0 END) as rejected_by_claude,
                SUM(CASE WHEN trend_filter_pass = 1 AND claude_pass = 1 AND execution_filter_pass = 0 THEN 1 ELSE 0 END) as rejected_by_exec,
                SUM(CASE WHEN executed = 1 THEN 1 ELSE 0 END) as executed
            FROM trade_tags
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        conn = db._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if not row or row['total'] == 0:
            return {'error': 'No data'}

        total = row['total']
        rejected_by_trend = row['rejected_by_trend']
        rejected_by_claude = row['rejected_by_claude']
        rejected_by_exec = row['rejected_by_exec']
        executed = row['executed']

        return {
            'total_signals': total,
            'executed': executed,
            'execution_rate': executed / total,

            'rejected_by_trend': rejected_by_trend,
            'rejected_by_claude': rejected_by_claude,
            'rejected_by_exec': rejected_by_exec,

            'rejection_rate_trend': rejected_by_trend / total,
            'rejection_rate_claude': rejected_by_claude / total,
            'rejection_rate_exec': rejected_by_exec / total,

            'total_rejected': total - executed,
            'total_rejection_rate': (total - executed) / total,
        }

    def _analyze_claude_performance(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        strategy: Optional[str]
    ) -> Dict:
        """
        分析Claude的性能
        - Claude拒绝的信号，如果执行会怎样？（需要影子模式数据）
        - Claude通过的信号，实际胜率如何？
        - Claude的置信度与实际结果的相关性
        """
        # Claude通过且执行的交易
        query = """
            SELECT
                pnl,
                pnl_pct,
                claude_confidence,
                claude_signal_quality
            FROM trade_tags
            WHERE claude_enabled = 1
              AND claude_pass = 1
              AND executed = 1
              AND pnl != 0
        """
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        conn = db._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        claude_trades = cursor.fetchall()
        conn.close()

        if not claude_trades:
            return {'error': 'No Claude trades'}

        # 统计
        total = len(claude_trades)
        wins = sum(1 for t in claude_trades if t['pnl'] > 0)
        win_rate = wins / total

        # 按置信度分组
        high_conf_trades = [t for t in claude_trades if t['claude_confidence'] >= 0.7]
        mid_conf_trades = [t for t in claude_trades if 0.5 <= t['claude_confidence'] < 0.7]
        low_conf_trades = [t for t in claude_trades if t['claude_confidence'] < 0.5]

        def calc_win_rate(trades):
            if not trades:
                return 0
            return sum(1 for t in trades if t['pnl'] > 0) / len(trades)

        # Claude拒绝的信号数量
        conn2 = db._get_conn()
        conn2.row_factory = sqlite3.Row
        cursor = conn2.execute("""
            SELECT COUNT(*) as count
            FROM trade_tags
            WHERE claude_enabled = 1 AND claude_pass = 0
        """)
        claude_rejects = cursor.fetchone()['count']
        conn2.close()

        return {
            'total_claude_trades': total,
            'win_rate': win_rate,
            'claude_rejects': claude_rejects,

            'high_confidence_trades': len(high_conf_trades),
            'high_confidence_win_rate': calc_win_rate(high_conf_trades),

            'mid_confidence_trades': len(mid_conf_trades),
            'mid_confidence_win_rate': calc_win_rate(mid_conf_trades),

            'low_confidence_trades': len(low_conf_trades),
            'low_confidence_win_rate': calc_win_rate(low_conf_trades),

            'avg_confidence': sum(t['claude_confidence'] for t in claude_trades) / total,
            'avg_signal_quality': sum(t['claude_signal_quality'] for t in claude_trades) / total,
        }

    def _analyze_execution_quality(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        strategy: Optional[str]
    ) -> Dict:
        """
        分析执行质量
        - 点差分布
        - 流动性分布
        - 波动率分布
        """
        query = """
            SELECT
                volume_ratio,
                volatility,
                atr
            FROM trade_tags
            WHERE executed = 1
        """
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        conn = db._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        trades = cursor.fetchall()
        conn.close()

        if not trades:
            return {'error': 'No trades'}

        volume_ratios = [t['volume_ratio'] for t in trades if t['volume_ratio']]
        volatilities = [t['volatility'] for t in trades if t['volatility']]
        atrs = [t['atr'] for t in trades if t['atr']]

        return {
            'avg_volume_ratio': sum(volume_ratios) / len(volume_ratios) if volume_ratios else 0,
            'min_volume_ratio': min(volume_ratios) if volume_ratios else 0,
            'max_volume_ratio': max(volume_ratios) if volume_ratios else 0,

            'avg_volatility': sum(volatilities) / len(volatilities) if volatilities else 0,
            'min_volatility': min(volatilities) if volatilities else 0,
            'max_volatility': max(volatilities) if volatilities else 0,

            'avg_atr': sum(atrs) / len(atrs) if atrs else 0,
        }

    def _analyze_risk_metrics(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        strategy: Optional[str]
    ) -> Dict:
        """
        分析风险指标
        - 最大单笔亏损
        - 平均持仓时间
        - MFE/MAE分析
        """
        query = """
            SELECT
                pnl,
                pnl_pct,
                hold_time_minutes,
                max_favorable_excursion,
                max_adverse_excursion
            FROM trade_tags
            WHERE executed = 1 AND pnl != 0
        """
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        conn = db._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        trades = cursor.fetchall()
        conn.close()

        if not trades:
            return {'error': 'No trades'}

        pnls = [t['pnl'] for t in trades]
        pnl_pcts = [t['pnl_pct'] for t in trades]
        hold_times = [t['hold_time_minutes'] for t in trades if t['hold_time_minutes']]
        mfes = [t['max_favorable_excursion'] for t in trades if t['max_favorable_excursion']]
        maes = [t['max_adverse_excursion'] for t in trades if t['max_adverse_excursion']]

        return {
            'max_single_loss': min(pnls),
            'max_single_loss_pct': min(pnl_pcts),
            'max_single_win': max(pnls),
            'max_single_win_pct': max(pnl_pcts),

            'avg_hold_time_minutes': sum(hold_times) / len(hold_times) if hold_times else 0,
            'min_hold_time_minutes': min(hold_times) if hold_times else 0,
            'max_hold_time_minutes': max(hold_times) if hold_times else 0,

            'avg_mfe': sum(mfes) / len(mfes) if mfes else 0,
            'avg_mae': sum(maes) / len(maes) if maes else 0,
        }

    def print_report(self, report: Dict):
        """打印格式化的报告"""
        print("\n" + "=" * 80)
        print("性能分析报告")
        print("=" * 80)

        # 时期
        period = report['period']
        print(f"\n时期: {period['start']} ~ {period['end']}")
        print(f"策略: {period['strategy']}")

        # 核心指标
        print("\n" + "-" * 80)
        print("核心指标（6个关键指标）")
        print("-" * 80)

        metrics = report['core_metrics']
        if 'error' not in metrics:
            print(f"总交易次数: {metrics['total_trades']}")
            print(f"胜率: {metrics['win_rate']:.2%} ({metrics['winning_trades']}胜 / {metrics['losing_trades']}负)")
            print(f"\n1. 最大回撤: {metrics['max_drawdown']:.2f} USDT ({metrics['max_drawdown_pct']:.2f}%)")
            print(f"2. 连续亏损P95: {metrics['loss_streak_p95']} 次 (最大: {metrics['max_loss_streak']})")
            print(f"3. 盈亏比: {metrics['profit_factor']:.2f}")
            print(f"4. 单笔期望: {metrics['expectancy_per_trade']:.2f} USDT")
            print(f"5. 平均滑点: {metrics['avg_slippage_per_trade']:.4f}%")
            print(f"6. 总盈亏: {metrics['total_pnl']:.2f} USDT")
            print(f"\n平均盈利: {metrics['avg_win']:.2f} USDT")
            print(f"平均亏损: {metrics['avg_loss']:.2f} USDT")
        else:
            print(f"错误: {metrics['error']}")

        # 拒绝分析
        print("\n" + "-" * 80)
        print("拒绝率分布")
        print("-" * 80)

        rejections = report['rejection_analysis']
        if 'error' not in rejections:
            print(f"总信号数: {rejections['total_signals']}")
            print(f"执行数: {rejections['executed']} ({rejections['execution_rate']:.1%})")
            print(f"\n各阶段拒绝:")
            print(f"  趋势过滤: {rejections['rejected_by_trend']} ({rejections['rejection_rate_trend']:.1%})")
            print(f"  Claude分析: {rejections['rejected_by_claude']} ({rejections['rejection_rate_claude']:.1%})")
            print(f"  执行层风控: {rejections['rejected_by_exec']} ({rejections['rejection_rate_exec']:.1%})")
            print(f"\n总拒绝: {rejections['total_rejected']} ({rejections['total_rejection_rate']:.1%})")
        else:
            print(f"错误: {rejections['error']}")

        # Claude分析
        print("\n" + "-" * 80)
        print("Claude性能分析")
        print("-" * 80)

        claude = report['claude_analysis']
        if 'error' not in claude:
            print(f"Claude交易数: {claude['total_claude_trades']}")
            print(f"Claude胜率: {claude['win_rate']:.2%}")
            print(f"Claude拒绝数: {claude['claude_rejects']}")
            print(f"\n按置信度分组:")
            print(f"  高置信度(≥0.7): {claude['high_confidence_trades']}笔, 胜率: {claude['high_confidence_win_rate']:.2%}")
            print(f"  中置信度(0.5-0.7): {claude['mid_confidence_trades']}笔, 胜率: {claude['mid_confidence_win_rate']:.2%}")
            print(f"  低置信度(<0.5): {claude['low_confidence_trades']}笔, 胜率: {claude['low_confidence_win_rate']:.2%}")
            print(f"\n平均置信度: {claude['avg_confidence']:.2f}")
            print(f"平均信号质量: {claude['avg_signal_quality']:.2f}")
        else:
            print(f"错误: {claude['error']}")

        # 执行质量
        print("\n" + "-" * 80)
        print("执行质量")
        print("-" * 80)

        exec_quality = report['execution_quality']
        if 'error' not in exec_quality:
            print(f"平均量比: {exec_quality['avg_volume_ratio']:.2f}")
            print(f"平均波动率: {exec_quality['avg_volatility']:.4f}")
            print(f"平均ATR: {exec_quality['avg_atr']:.2f}")
        else:
            print(f"错误: {exec_quality['error']}")

        # 风险指标
        print("\n" + "-" * 80)
        print("风险指标")
        print("-" * 80)

        risk = report['risk_analysis']
        if 'error' not in risk:
            print(f"最大单笔亏损: {risk['max_single_loss']:.2f} USDT ({risk['max_single_loss_pct']:.2f}%)")
            print(f"最大单笔盈利: {risk['max_single_win']:.2f} USDT ({risk['max_single_win_pct']:.2f}%)")
            print(f"平均持仓时间: {risk['avg_hold_time_minutes']:.0f} 分钟")
            print(f"平均MFE: {risk['avg_mfe']:.2f}")
            print(f"平均MAE: {risk['avg_mae']:.2f}")
        else:
            print(f"错误: {risk['error']}")

        print("\n" + "=" * 80)

    def export_to_csv(self, report: Dict, filename: str = "performance_report.csv"):
        """导出报告为CSV"""
        import csv

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # 写入核心指标
            writer.writerow(['Metric', 'Value'])
            metrics = report['core_metrics']
            if 'error' not in metrics:
                writer.writerow(['Total Trades', metrics['total_trades']])
                writer.writerow(['Win Rate', f"{metrics['win_rate']:.2%}"])
                writer.writerow(['Max Drawdown', f"{metrics['max_drawdown']:.2f}"])
                writer.writerow(['Max Drawdown %', f"{metrics['max_drawdown_pct']:.2f}%"])
                writer.writerow(['Loss Streak P95', metrics['loss_streak_p95']])
                writer.writerow(['Profit Factor', f"{metrics['profit_factor']:.2f}"])
                writer.writerow(['Expectancy per Trade', f"{metrics['expectancy_per_trade']:.2f}"])
                writer.writerow(['Total PNL', f"{metrics['total_pnl']:.2f}"])

        logger.info(f"报告已导出到: {filename}")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='性能分析器')
    parser.add_argument('--start', type=str, help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--strategy', type=str, help='策略名称')
    parser.add_argument('--export', type=str, help='导出CSV文件名')

    args = parser.parse_args()

    analyzer = PerformanceAnalyzer()
    report = analyzer.analyze_period(
        start_date=args.start,
        end_date=args.end,
        strategy=args.strategy
    )

    analyzer.print_report(report)

    if args.export:
        analyzer.export_to_csv(report, args.export)


if __name__ == "__main__":
    main()
