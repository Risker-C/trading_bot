"""
SQLite适配器 - 实现IDataRepository接口
"""
import sqlite3
import zlib
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd

from backtest.domain.interfaces import IDataRepository


class SQLiteRepository(IDataRepository):
    """SQLite存储适配器"""

    def __init__(self, db_path: str = "backtest.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        """获取数据库连接（WAL模式）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """初始化数据库Schema"""
        conn = self._get_conn()

        # 创建所有表（使用 IF NOT EXISTS 确保幂等性）
        conn.executescript("""
            -- 策略版本管理
            CREATE TABLE IF NOT EXISTS strategy_versions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                params_schema TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(name, version)
            );

            -- 参数集
            CREATE TABLE IF NOT EXISTS parameter_sets (
                id TEXT PRIMARY KEY,
                strategy_version_id TEXT NOT NULL,
                params TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (strategy_version_id) REFERENCES strategy_versions(id)
            );

            -- K线数据集（去重+压缩）
            CREATE TABLE IF NOT EXISTS kline_datasets (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                start_ts INTEGER NOT NULL,
                end_ts INTEGER NOT NULL,
                checksum TEXT NOT NULL,
                data BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(symbol, timeframe, start_ts, end_ts)
            );

            -- 回测运行
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id TEXT PRIMARY KEY,
                kline_dataset_id TEXT NOT NULL,
                strategy_version_id TEXT NOT NULL,
                param_set_id TEXT,
                filter_set TEXT,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (kline_dataset_id) REFERENCES kline_datasets(id),
                FOREIGN KEY (strategy_version_id) REFERENCES strategy_versions(id),
                FOREIGN KEY (param_set_id) REFERENCES parameter_sets(id)
            );

            -- 回测指标（完整）
            CREATE TABLE IF NOT EXISTS backtest_metrics (
                run_id TEXT PRIMARY KEY,
                total_trades INTEGER,
                win_rate REAL,
                total_pnl REAL,
                total_return REAL,
                max_drawdown REAL,
                sharpe REAL,
                sortino REAL,
                profit_factor REAL,
                expectancy REAL,
                avg_win REAL,
                avg_loss REAL,
                metrics TEXT,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            );

            -- 优化任务
            CREATE TABLE IF NOT EXISTS optimization_jobs (
                id TEXT PRIMARY KEY,
                strategy_version_id TEXT NOT NULL,
                kline_dataset_id TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                search_space TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (strategy_version_id) REFERENCES strategy_versions(id),
                FOREIGN KEY (kline_dataset_id) REFERENCES kline_datasets(id)
            );

            -- 优化结果
            CREATE TABLE IF NOT EXISTS optimization_results (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                param_set_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                rank INTEGER,
                score REAL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (job_id) REFERENCES optimization_jobs(id),
                FOREIGN KEY (param_set_id) REFERENCES parameter_sets(id),
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            );

            -- 分析报告
            CREATE TABLE IF NOT EXISTS backtest_reports (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                recommendations TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_runs_status ON backtest_runs(status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_strategy ON backtest_runs(strategy_version_id);
            CREATE INDEX IF NOT EXISTS idx_opt_results_job_rank ON optimization_results(job_id, rank);
        """)
        conn.commit()
        conn.close()

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> pd.DataFrame:
        """获取K线数据"""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT data FROM kline_datasets
            WHERE symbol = ? AND timeframe = ?
            AND start_ts <= ? AND end_ts >= ?
            ORDER BY created_at DESC LIMIT 1
        """, (symbol, timeframe, start_ts, end_ts))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return pd.DataFrame()

        # 解压数据
        compressed_data = row[0]
        json_data = zlib.decompress(compressed_data).decode()
        klines = json.loads(json_data)

        df = pd.DataFrame(klines)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df

    async def save_kline_dataset(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        data: bytes
    ) -> str:
        """保存K线数据集（压缩）"""
        dataset_id = str(uuid.uuid4())
        checksum = str(hash(data))
        now = int(datetime.utcnow().timestamp())

        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO kline_datasets
            (id, symbol, timeframe, start_ts, end_ts, checksum, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (dataset_id, symbol, timeframe, start_ts, end_ts, checksum, data, now))
        conn.commit()
        conn.close()

        return dataset_id

    async def create_backtest_run(self, params: Dict[str, Any]) -> str:
        """创建回测运行"""
        run_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        conn = self._get_conn()
        conn.execute("""
            INSERT INTO backtest_runs
            (id, kline_dataset_id, strategy_version_id, param_set_id, filter_set, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            params['kline_dataset_id'],
            params['strategy_version_id'],
            params.get('param_set_id'),
            json.dumps(params.get('filter_set', {})),
            'created',
            now
        ))
        conn.commit()
        conn.close()

        return run_id

    async def update_run_status(self, run_id: str, status: str) -> None:
        """更新运行状态"""
        conn = self._get_conn()
        conn.execute("UPDATE backtest_runs SET status = ? WHERE id = ?", (status, run_id))
        conn.commit()
        conn.close()

    async def save_metrics(self, run_id: str, metrics: Dict[str, Any]) -> None:
        """保存回测指标"""
        conn = self._get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO backtest_metrics
            (run_id, total_trades, win_rate, total_pnl, total_return,
             max_drawdown, sharpe, sortino, profit_factor, expectancy,
             avg_win, avg_loss, metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            metrics.get('total_trades', 0),
            metrics.get('win_rate', 0.0),
            metrics.get('total_pnl', 0.0),
            metrics.get('total_return', 0.0),
            metrics.get('max_drawdown', 0.0),
            metrics.get('sharpe', 0.0),
            metrics.get('sortino', 0.0),
            metrics.get('profit_factor', 0.0),
            metrics.get('expectancy', 0.0),
            metrics.get('avg_win', 0.0),
            metrics.get('avg_loss', 0.0),
            json.dumps(metrics)
        ))
        conn.commit()
        conn.close()

    async def load_kline_dataset(self, kline_dataset_id: str) -> pd.DataFrame:
        """加载K线数据集"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT data FROM kline_datasets WHERE id = ?", (kline_dataset_id,))
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"K线数据集不存在: {kline_dataset_id}")

            compressed_data = row[0]
            json_data = zlib.decompress(compressed_data).decode()
            klines = json.loads(json_data)

            df = pd.DataFrame(klines)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        finally:
            conn.close()

    async def get_strategy_version(self, strategy_version_id: str) -> Dict[str, Any]:
        """获取策略版本信息"""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT id, name, version, params_schema, code_hash, created_at
                FROM strategy_versions WHERE id = ?
            """, (strategy_version_id,))
            row = cursor.fetchone()

            if not row:
                raise ValueError(f"策略版本不存在: {strategy_version_id}")

            return {
                'id': row[0],
                'name': row[1],
                'version': row[2],
                'params_schema': json.loads(row[3]),
                'code_hash': row[4],
                'created_at': row[5]
            }
        finally:
            conn.close()
