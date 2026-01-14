import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from utils.logger_utils import TradeDatabase, get_logger


class StatisticsService:
    """统计分析服务"""

    def __init__(self, db: TradeDatabase = None):
        self.db = db or TradeDatabase()
        self.logger = get_logger(__name__)

    async def get_daily_statistics(self) -> Dict[str, Any]:
        """获取日统计数据"""
        today = datetime.now().strftime('%Y-%m-%d')

        stats = await asyncio.to_thread(self._calculate_period_stats, today, today)
        stats['period'] = 'daily'
        stats['date'] = today

        return stats

    async def get_weekly_statistics(self) -> Dict[str, Any]:
        """获取周统计数据"""
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
        week_end = today.strftime('%Y-%m-%d')

        stats = await asyncio.to_thread(self._calculate_period_stats, week_start, week_end)
        stats['period'] = 'weekly'
        stats['start_date'] = week_start
        stats['end_date'] = week_end

        # 添加策略对比
        strategy_stats = await asyncio.to_thread(self._get_strategy_comparison, week_start, week_end)
        stats['strategy_comparison'] = strategy_stats

        return stats

    async def get_monthly_statistics(self) -> Dict[str, Any]:
        """获取月统计数据"""
        today = datetime.now()
        month_start = today.replace(day=1).strftime('%Y-%m-%d')
        month_end = today.strftime('%Y-%m-%d')

        stats = await asyncio.to_thread(self._calculate_period_stats, month_start, month_end)
        stats['period'] = 'monthly'
        stats['start_date'] = month_start
        stats['end_date'] = month_end

        # 添加策略对比
        strategy_stats = await asyncio.to_thread(self._get_strategy_comparison, month_start, month_end)
        stats['strategy_comparison'] = strategy_stats

        return stats

    async def get_strategy_comparison(self, start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """获取策略对比数据"""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        return await asyncio.to_thread(self._get_strategy_comparison, start_date, end_date)

    def _calculate_period_stats(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """计算指定时间段的统计数据"""
        conn = self.db._get_conn()
        cursor = conn.cursor()

        # 获取交易总数
        cursor.execute('''
            SELECT COUNT(*) FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
        ''', (start_date, end_date))
        total_trades = cursor.fetchone()[0]

        # 获取总盈亏
        cursor.execute('''
            SELECT SUM(pnl) FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            AND pnl IS NOT NULL
        ''', (start_date, end_date))
        total_pnl = cursor.fetchone()[0] or 0

        # 获取盈利交易数
        cursor.execute('''
            SELECT COUNT(*) FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            AND pnl > 0
        ''', (start_date, end_date))
        winning_trades = cursor.fetchone()[0]

        # 获取亏损交易数
        cursor.execute('''
            SELECT COUNT(*) FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            AND pnl < 0
        ''', (start_date, end_date))
        losing_trades = cursor.fetchone()[0]

        # 计算胜率
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # 获取平均盈利
        cursor.execute('''
            SELECT AVG(pnl) FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            AND pnl > 0
        ''', (start_date, end_date))
        avg_profit = cursor.fetchone()[0] or 0

        # 获取平均亏损
        cursor.execute('''
            SELECT AVG(pnl) FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            AND pnl < 0
        ''', (start_date, end_date))
        avg_loss = cursor.fetchone()[0] or 0

        # 计算盈亏比
        profit_loss_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else 0

        conn.close()

        return {
            'total_trades': total_trades,
            'total_pnl': round(total_pnl, 2),
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'avg_profit': round(avg_profit, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_loss_ratio': round(profit_loss_ratio, 2)
        }

    def _get_strategy_comparison(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取策略对比数据"""
        conn = self.db._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                strategy,
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl
            FROM trades
            WHERE date(created_at) >= ? AND date(created_at) <= ?
            AND strategy IS NOT NULL
            GROUP BY strategy
            ORDER BY total_pnl DESC
        ''', (start_date, end_date))

        rows = cursor.fetchall()
        conn.close()

        strategies = []
        for row in rows:
            strategy_name = row[0]
            total_trades = row[1]
            winning_trades = row[2]
            total_pnl = row[3] or 0
            avg_pnl = row[4] or 0
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            strategies.append({
                'strategy': strategy_name,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'avg_pnl': round(avg_pnl, 2)
            })

        return strategies
