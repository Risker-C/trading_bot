"""
自动清理服务 - 定期清理旧数据以控制存储占用
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any


class CleanupService:
    """自动清理服务"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path

    async def cleanup_old_data(
        self,
        keep_days: int = 90,
        keep_recent_runs: int = 100,
        keep_optimization: bool = True
    ) -> Dict[str, Any]:
        """
        清理旧数据

        Args:
            keep_days: 保留最近N天的数据
            keep_recent_runs: 保留最近N次回测
            keep_optimization: 是否保留优化任务相关数据

        Returns:
            清理统计
        """
        conn = sqlite3.connect(self.db_path)
        stats = {
            'deleted_runs': 0,
            'deleted_trades': 0,
            'deleted_klines': 0,
            'deleted_equity': 0
        }

        try:
            # 1. 删除90天前的回测记录（保留优化任务）
            cutoff_ts = int((datetime.utcnow() - timedelta(days=keep_days)).timestamp())

            if keep_optimization:
                # 获取优化任务相关的run_id
                cursor = conn.execute("""
                    SELECT run_id FROM optimization_results
                """)
                optimization_run_ids = [row[0] for row in cursor.fetchall()]

                # 删除旧的非优化回测
                cursor = conn.execute("""
                    DELETE FROM backtest_runs
                    WHERE created_at < ?
                    AND id NOT IN (
                        SELECT id FROM backtest_runs
                        ORDER BY created_at DESC LIMIT ?
                    )
                    AND id NOT IN ({})
                """.format(','.join('?' * len(optimization_run_ids))),
                    [cutoff_ts, keep_recent_runs] + optimization_run_ids
                )
            else:
                cursor = conn.execute("""
                    DELETE FROM backtest_runs
                    WHERE created_at < ?
                    AND id NOT IN (
                        SELECT id FROM backtest_runs
                        ORDER BY created_at DESC LIMIT ?
                    )
                """, (cutoff_ts, keep_recent_runs))

            stats['deleted_runs'] = cursor.rowcount

            # 2. 删除孤立的交易记录
            cursor = conn.execute("""
                DELETE FROM backtest_trades
                WHERE session_id NOT IN (SELECT id FROM backtest_runs)
            """)
            stats['deleted_trades'] = cursor.rowcount

            # 3. 删除孤立的权益曲线
            cursor = conn.execute("""
                DELETE FROM backtest_equity_curve
                WHERE session_id NOT IN (SELECT id FROM backtest_runs)
            """)
            stats['deleted_equity'] = cursor.rowcount

            # 4. 删除未被引用的K线数据集
            cursor = conn.execute("""
                DELETE FROM kline_datasets
                WHERE id NOT IN (SELECT DISTINCT kline_dataset_id FROM backtest_runs)
            """)
            stats['deleted_klines'] = cursor.rowcount

            conn.commit()

            # 5. 压缩数据库
            conn.execute("VACUUM")

            return stats

        finally:
            conn.close()

    async def get_cleanup_preview(self, keep_days: int = 90) -> Dict[str, Any]:
        """预览清理操作（不实际删除）"""
        conn = sqlite3.connect(self.db_path)
        cutoff_ts = int((datetime.utcnow() - timedelta(days=keep_days)).timestamp())

        cursor = conn.execute("""
            SELECT COUNT(*) FROM backtest_runs WHERE created_at < ?
        """, (cutoff_ts,))
        old_runs = cursor.fetchone()[0]

        cursor = conn.execute("""
            SELECT COUNT(*) FROM backtest_trades
            WHERE session_id NOT IN (SELECT id FROM backtest_runs)
        """)
        orphan_trades = cursor.fetchone()[0]

        cursor = conn.execute("""
            SELECT COUNT(*) FROM kline_datasets
            WHERE id NOT IN (SELECT DISTINCT kline_dataset_id FROM backtest_runs)
        """)
        orphan_klines = cursor.fetchone()[0]

        conn.close()

        return {
            'old_runs': old_runs,
            'orphan_trades': orphan_trades,
            'orphan_klines': orphan_klines,
            'estimated_space_freed_mb': (old_runs * 0.5 + orphan_klines * 10)
        }
