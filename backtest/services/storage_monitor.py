"""
存储监控服务 - 监控数据库大小和使用情况
"""
import os
import sqlite3
from typing import Dict, Any


class StorageMonitor:
    """存储监控服务"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path
        self.limit_gb = 10

    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""

        # 数据库文件大小
        if not os.path.exists(self.db_path):
            return {
                'total_size_mb': 0,
                'limit_mb': self.limit_gb * 1024,
                'usage_percent': 0,
                'breakdown': {}
            }

        db_size = os.path.getsize(self.db_path)
        db_size_mb = db_size / (1024 * 1024)
        limit_mb = self.limit_gb * 1024
        usage_percent = (db_size_mb / limit_mb) * 100

        # 各表大小
        breakdown = self._get_table_sizes()

        return {
            'total_size_mb': round(db_size_mb, 2),
            'limit_mb': limit_mb,
            'usage_percent': round(usage_percent, 2),
            'breakdown': breakdown,
            'warning': usage_percent > 80,
            'critical': usage_percent > 95
        }

    def _get_table_sizes(self) -> Dict[str, float]:
        """获取各表大小（MB）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        tables = [
            'kline_datasets',
            'backtest_runs',
            'backtest_trades',
            'backtest_equity_curve',
            'backtest_metrics',
            'optimization_results'
        ]

        breakdown = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]

                # 估算大小（粗略）
                cursor.execute(f"SELECT SUM(LENGTH(CAST(* AS TEXT))) FROM {table} LIMIT 1000")
                sample_size = cursor.fetchone()[0] or 0
                estimated_size_mb = (sample_size * count / 1000) / (1024 * 1024)

                breakdown[table] = round(estimated_size_mb, 2)
            except:
                breakdown[table] = 0

        conn.close()
        return breakdown

    def should_cleanup(self) -> bool:
        """是否需要清理"""
        stats = self.get_storage_stats()
        return stats['usage_percent'] > 80
