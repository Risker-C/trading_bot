"""
日志和数据库工具 - 增强版
"""
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import numpy as np

import config

# 创建日志目录
LOG_DIR = getattr(config, 'LOG_DIR', 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


class LevelFilter(logging.Filter):
    """
    日志级别过滤器
    用于精确控制每个 handler 只接收特定级别的日志
    """
    def __init__(self, level: int, exact: bool = True):
        """
        初始化过滤器

        Args:
            level: 日志级别 (logging.DEBUG, logging.INFO, etc.)
            exact: 是否精确匹配级别
                   True: 只接收该级别的日志
                   False: 接收该级别及以上的日志
        """
        super().__init__()
        self.level = level
        self.exact = exact

    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录

        Args:
            record: 日志记录对象

        Returns:
            True: 接收该日志
            False: 拒绝该日志
        """
        if self.exact:
            # 精确匹配：只接收指定级别的日志
            return record.levelno == self.level
        else:
            # 范围匹配：接收指定级别及以上的日志
            return record.levelno >= self.level


def get_logger(name: str) -> logging.Logger:
    """
    获取 logger 实例（支持日志分流）

    架构设计：
    - 存储层：多个文件 handler，按级别分流存储
      * debug.log: DEBUG 级别日志
      * info.log: INFO 级别日志
      * warning.log: WARNING 级别日志
      * error.log: ERROR 级别日志
    - 观察层：控制台 handler，聚合显示所有级别日志

    Args:
        name: logger 名称（通常是模块名）

    Returns:
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        # 从 config 获取日志级别，兼容旧配置
        log_level = getattr(config, 'LOG_LEVEL', 'DEBUG')
        logger.setLevel(getattr(logging, log_level, logging.DEBUG))

        # 检查是否启用日志分流
        enable_splitting = getattr(config, 'ENABLE_LOG_SPLITTING', True)

        if enable_splitting:
            # ========== 新架构：日志分流 ==========

            # 获取日志轮转配置
            rotation_when = getattr(config, 'LOG_ROTATION_WHEN', 'midnight')
            rotation_interval = getattr(config, 'LOG_ROTATION_INTERVAL', 1)
            rotation_backup_count = getattr(config, 'LOG_ROTATION_BACKUP_COUNT', 30)

            # 统一的日志格式
            file_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # 1. DEBUG 日志文件 handler
            debug_file = getattr(config, 'LOG_FILE_DEBUG', 'debug.log')
            debug_handler = TimedRotatingFileHandler(
                os.path.join(LOG_DIR, debug_file),
                when=rotation_when,
                interval=rotation_interval,
                backupCount=rotation_backup_count,
                encoding='utf-8'
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(file_format)
            debug_handler.addFilter(LevelFilter(logging.DEBUG, exact=True))
            logger.addHandler(debug_handler)

            # 2. INFO 日志文件 handler
            info_file = getattr(config, 'LOG_FILE_INFO', 'info.log')
            info_handler = TimedRotatingFileHandler(
                os.path.join(LOG_DIR, info_file),
                when=rotation_when,
                interval=rotation_interval,
                backupCount=rotation_backup_count,
                encoding='utf-8'
            )
            info_handler.setLevel(logging.INFO)
            info_handler.setFormatter(file_format)
            info_handler.addFilter(LevelFilter(logging.INFO, exact=True))
            logger.addHandler(info_handler)

            # 3. WARNING 日志文件 handler
            warning_file = getattr(config, 'LOG_FILE_WARNING', 'warning.log')
            warning_handler = TimedRotatingFileHandler(
                os.path.join(LOG_DIR, warning_file),
                when=rotation_when,
                interval=rotation_interval,
                backupCount=rotation_backup_count,
                encoding='utf-8'
            )
            warning_handler.setLevel(logging.WARNING)
            warning_handler.setFormatter(file_format)
            warning_handler.addFilter(LevelFilter(logging.WARNING, exact=True))
            logger.addHandler(warning_handler)

            # 4. ERROR 日志文件 handler（包含 ERROR 和 CRITICAL）
            error_file = getattr(config, 'LOG_FILE_ERROR', 'error.log')
            error_handler = TimedRotatingFileHandler(
                os.path.join(LOG_DIR, error_file),
                when=rotation_when,
                interval=rotation_interval,
                backupCount=rotation_backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(file_format)
            # ERROR handler 不使用精确匹配，接收 ERROR 和 CRITICAL
            error_handler.addFilter(LevelFilter(logging.ERROR, exact=False))
            logger.addHandler(error_handler)

            # 5. 控制台 handler（观察层：聚合显示所有级别）
            console_handler = logging.StreamHandler()
            console_log_level = getattr(config, 'CONSOLE_LOG_LEVEL', 'INFO')
            console_handler.setLevel(getattr(logging, console_log_level, logging.INFO))

            # 控制台格式（更简洁，适合实时观察）
            console_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_format)

            # 如果配置了显示所有级别，则不添加过滤器
            show_all_levels = getattr(config, 'CONSOLE_SHOW_ALL_LEVELS', True)
            if not show_all_levels:
                # 只显示指定级别及以上
                console_handler.addFilter(LevelFilter(
                    getattr(logging, console_log_level, logging.INFO),
                    exact=False
                ))

            logger.addHandler(console_handler)

        else:
            # ========== 旧架构：单文件日志（兼容模式）==========

            # 控制台输出
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_format)

            # 文件输出 - 使用日志轮转
            log_file = getattr(config, 'LOG_FILE', 'trading_bot.log')
            file_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, log_file),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,  # 保留5个备份
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)

            logger.addHandler(console_handler)
            logger.addHandler(file_handler)

    return logger


class MetricsLogger:
    """轻量级性能指标记录器（Phase 0）"""

    def __init__(self):
        self.logger = logging.getLogger("metrics")
        self.metrics = {}

    def record_latency(self, operation: str, latency_ms: float):
        """记录操作延迟（毫秒）"""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(latency_ms)
        self.logger.debug(f"{operation}: {latency_ms:.2f}ms")

    def record_memory(self, label: str, memory_mb: float):
        """记录内存使用（MB）"""
        self.logger.debug(f"Memory [{label}]: {memory_mb:.2f}MB")

    def get_stats(self, operation: str) -> Dict:
        """获取操作的统计信息"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}

        latencies = self.metrics[operation]
        return {
            'count': len(latencies),
            'avg': sum(latencies) / len(latencies),
            'min': min(latencies),
            'max': max(latencies)
        }


class TradeDatabase:
    """交易记录数据库"""
    
    def __init__(self, db_file: str = None):
        # 兼容不同配置名
        default_db = getattr(config, 'DB_FILE', None) or getattr(config, 'DB_PATH', 'trading_bot.db')
        self.db_file = db_file or default_db
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_file)

        # 启用 WAL 模式以提升并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

        cursor = conn.cursor()
        
        # 交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                symbol TEXT,
                side TEXT,
                action TEXT,
                amount REAL,
                price REAL,
                value_usdt REAL,
                pnl REAL,
                pnl_percent REAL,
                strategy TEXT,
                reason TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # P1优化：添加新字段以支持完整的交易数据记录
        # 检查并添加缺失的字段（兼容已存在的数据库）
        try:
            # 获取现有字段列表
            cursor.execute("PRAGMA table_info(trades)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # 添加 filled_price 字段（实际成交价）
            if 'filled_price' not in existing_columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN filled_price REAL')

            # 添加 filled_time 字段（实际成交时间）
            if 'filled_time' not in existing_columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN filled_time TIMESTAMP')

            # 添加 fee 字段（手续费）
            if 'fee' not in existing_columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN fee REAL')

            # 添加 fee_currency 字段（手续费币种）
            if 'fee_currency' not in existing_columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN fee_currency TEXT')

            # 添加 batch_number 字段（批次号，用于分批操作）
            if 'batch_number' not in existing_columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN batch_number INTEGER')

            # 添加 remaining_amount 字段（剩余持仓量，用于部分平仓）
            if 'remaining_amount' not in existing_columns:
                cursor.execute('ALTER TABLE trades ADD COLUMN remaining_amount REAL')

        except Exception as e:
            # 如果添加字段失败，记录错误但不影响程序运行
            print(f"Warning: Failed to add new columns to trades table: {e}")
        
        # 持仓快照表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS position_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                amount REAL,
                entry_price REAL,
                current_price REAL,
                unrealized_pnl REAL,
                leverage INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 策略信号表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT,
                signal TEXT,
                reason TEXT,
                strength REAL,
                confidence REAL,
                indicators TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 账户余额快照表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total REAL,
                free REAL,
                used REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 风控事件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                description TEXT,
                current_price REAL,
                trigger_price REAL,
                position_side TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 每日统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                total_pnl REAL,
                max_drawdown REAL,
                starting_balance REAL,
                ending_balance REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ========== 新增：权益曲线表 ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equity REAL,
                balance REAL,
                drawdown REAL,
                peak_equity REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ========== 新增：风险指标表 ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS risk_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_trades INTEGER,
                win_rate REAL,
                profit_factor REAL,
                expectancy REAL,
                max_drawdown REAL,
                kelly_fraction REAL,
                consecutive_losses INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_file)
        # 启用 WAL 模式以提升并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    
    def log_trade(
        self,
        symbol: str,
        side: str,
        action: str,
        amount: float,
        price: float,
        order_id: str = "",
        value_usdt: float = 0,
        pnl: float = 0,
        pnl_percent: float = 0,
        strategy: str = "",
        reason: str = "",
        status: str = "filled",
        # P1优化：新增字段以支持完整的交易数据记录
        filled_price: float = None,
        filled_time: str = None,
        fee: float = None,
        fee_currency: str = None,
        batch_number: int = None,
        remaining_amount: float = None
    ) -> int:
        """
        记录交易（P1优化：支持完整的交易数据记录）

        新增参数：
        - filled_price: 实际成交价（可能与price不同）
        - filled_time: 实际成交时间
        - fee: 手续费
        - fee_currency: 手续费币种
        - batch_number: 批次号（用于分批操作）
        - remaining_amount: 剩余持仓量（用于部分平仓）
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # 自动计算 value_usdt
        if value_usdt == 0:
            value_usdt = amount * price

        cursor.execute('''
            INSERT INTO trades (
                order_id, symbol, side, action, amount, price,
                value_usdt, pnl, pnl_percent, strategy, reason, status,
                filled_price, filled_time, fee, fee_currency, batch_number, remaining_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id, symbol, side, action, amount, price,
            value_usdt, pnl, pnl_percent, strategy, reason, status,
            filled_price, filled_time, fee, fee_currency, batch_number, remaining_amount
        ))

        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return trade_id
    
    def log_signal(
        self,
        strategy: str,
        signal: str,
        reason: str,
        strength: float = 1.0,
        confidence: float = 1.0,
        indicators: Dict = None
    ) -> int:
        """记录策略信号（新增 confidence 参数）"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # 转换 numpy 类型为 Python 类型
        strength = float(strength) if strength is not None else 1.0
        confidence = float(confidence) if confidence is not None else 1.0

        # 转换 indicators 中的 numpy 类型为 Python 类型
        def convert_numpy_types(obj):
            """递归转换 numpy 类型为 Python 原生类型"""
            if obj is None:
                return None
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif isinstance(obj, np.ndarray):
                # numpy 数组转为列表
                return obj.tolist()
            elif isinstance(obj, (np.integer, np.floating)):
                # numpy 数值类型转为 Python 数值
                return obj.item()
            elif isinstance(obj, np.bool_):
                # numpy 布尔类型转为 Python 布尔
                return bool(obj)
            elif hasattr(obj, 'item') and hasattr(obj, 'dtype'):
                # 其他 numpy 标量类型
                return obj.item()
            else:
                return obj

        indicators_clean = convert_numpy_types(indicators or {})
        indicators_json = json.dumps(indicators_clean)

        cursor.execute('''
            INSERT INTO signals (strategy, signal, reason, strength, confidence, indicators)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (strategy, signal, reason, strength, confidence, indicators_json))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return signal_id
    
    def log_position_snapshot(
        self,
        symbol: str,
        side: str,
        amount: float,
        entry_price: float,
        current_price: float,
        unrealized_pnl: float,
        leverage: int,
        highest_price: float = 0,
        lowest_price: float = 0,
        entry_time: str = None
    ):
        """记录持仓快照"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO position_snapshots (
                symbol, side, amount, entry_price, current_price,
                unrealized_pnl, leverage, highest_price, lowest_price, entry_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, side, amount, entry_price, current_price, unrealized_pnl, leverage,
              highest_price, lowest_price, entry_time))

        conn.commit()
        conn.close()

    def get_latest_position_snapshot(self, symbol: str) -> dict:
        """获取最新的持仓快照"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT symbol, side, amount, entry_price, current_price,
                   unrealized_pnl, leverage, highest_price, lowest_price, entry_time, created_at
            FROM position_snapshots
            WHERE symbol = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (symbol,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'symbol': row[0],
                'side': row[1],
                'amount': row[2],
                'entry_price': row[3],
                'current_price': row[4],
                'unrealized_pnl': row[5],
                'leverage': row[6],
                'highest_price': row[7] or 0,
                'lowest_price': row[8] or 0,
                'entry_time': row[9],
                'created_at': row[10]
            }
        return None

    def get_position_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """获取持仓历史快照列表"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 构建查询条件
        conditions = []
        params = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol)

        if start_date:
            conditions.append("date(created_at) >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("date(created_at) <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f'''
            SELECT * FROM position_snapshots
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        '''

        params.extend([limit, offset])
        cursor.execute(query, params)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def log_balance_snapshot(self, total: float, free: float, used: float):
        """记录余额快照"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO balance_snapshots (total, free, used)
            VALUES (?, ?, ?)
        ''', (total, free, used))
        
        conn.commit()
        conn.close()
    
    def log_risk_event(
        self,
        event_type: str,
        description: str,
        current_price: float = 0,
        trigger_price: float = 0,
        position_side: str = ""
    ):
        """记录风控事件"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO risk_events (
                event_type, description, current_price, trigger_price, position_side
            ) VALUES (?, ?, ?, ?, ?)
        ''', (event_type, description, current_price, trigger_price, position_side))
        
        conn.commit()
        conn.close()
    
    # ========== 新增方法 ==========
    
    def log_equity(
        self,
        equity: float,
        balance: float,
        drawdown: float,
        peak_equity: float
    ):
        """记录权益曲线点"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO equity_curve (equity, balance, drawdown, peak_equity)
            VALUES (?, ?, ?, ?)
        ''', (equity, balance, drawdown, peak_equity))
        
        conn.commit()
        conn.close()
    
    def log_risk_metrics(
        self,
        total_trades: int,
        win_rate: float,
        profit_factor: float,
        expectancy: float,
        max_drawdown: float,
        kelly_fraction: float,
        consecutive_losses: int
    ):
        """记录风险指标快照"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO risk_metrics (
                total_trades, win_rate, profit_factor, expectancy,
                max_drawdown, kelly_fraction, consecutive_losses
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            total_trades, win_rate, profit_factor, expectancy,
            max_drawdown, kelly_fraction, consecutive_losses
        ))
        
        conn.commit()
        conn.close()
    
    def get_equity_curve(self, limit: int = 1000) -> List[Dict]:
        """获取权益曲线数据"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM equity_curve
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in reversed(rows)]
    
    def get_latest_risk_metrics(self) -> Optional[Dict]:
        """获取最新风险指标"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM risk_metrics
            ORDER BY created_at DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    # ========== 原有方法保持不变 ==========
    
    def update_daily_stats(
        self,
        date: str,
        total_trades: int,
        winning_trades: int,
        losing_trades: int,
        total_pnl: float,
        max_drawdown: float,
        starting_balance: float,
        ending_balance: float
    ):
        """更新每日统计"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_stats (
                date, total_trades, winning_trades, losing_trades,
                total_pnl, max_drawdown, starting_balance, ending_balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date, total_trades, winning_trades, losing_trades,
            total_pnl, max_drawdown, starting_balance, ending_balance
        ))
        
        conn.commit()
        conn.close()
    
    def get_trades(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取交易记录"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM trades
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_trade_by_id(self, trade_id: int) -> Optional[Dict]:
        """根据 ID 获取单个交易详情"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM trades
            WHERE id = ?
        ''', (trade_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_today_trades(self) -> List[Dict]:
        """获取今日交易"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT * FROM trades
            WHERE date(created_at) = ?
            ORDER BY created_at DESC
        ''', (today,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_today_pnl(self) -> float:
        """获取今日盈亏"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT COALESCE(SUM(pnl), 0) FROM trades
            WHERE date(created_at) = ?
        ''', (today,))
        
        result = cursor.fetchone()[0]
        conn.close()
        
        return float(result)
    
    def get_statistics(self, days: int = 30) -> Dict:
        """获取统计数据"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 总交易次数
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        # 盈利交易
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl > 0')
        winning_trades = cursor.fetchone()[0]
        
        # 亏损交易
        cursor.execute('SELECT COUNT(*) FROM trades WHERE pnl < 0')
        losing_trades = cursor.fetchone()[0]
        
        # 总盈亏
        cursor.execute('SELECT COALESCE(SUM(pnl), 0) FROM trades')
        total_pnl = cursor.fetchone()[0]
        
        # 平均盈亏
        cursor.execute('SELECT COALESCE(AVG(pnl), 0) FROM trades WHERE pnl != 0')
        avg_pnl = cursor.fetchone()[0]
        
        # 最大单笔盈利
        cursor.execute('SELECT COALESCE(MAX(pnl), 0) FROM trades')
        max_profit = cursor.fetchone()[0]
        
        # 最大单笔亏损
        cursor.execute('SELECT COALESCE(MIN(pnl), 0) FROM trades')
        max_loss = cursor.fetchone()[0]
        
        # ========== 新增：盈亏比计算 ==========
        cursor.execute('SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl > 0')
        total_wins = cursor.fetchone()[0]
        
        cursor.execute('SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE pnl < 0')
        total_losses = cursor.fetchone()[0]
        
        profit_factor = abs(total_wins / total_losses) if total_losses != 0 else 0
        
        conn.close()
        
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'profit_factor': profit_factor,
        }
    
    def get_signals(self, limit: int = 50) -> List[Dict]:
        """获取最近的策略信号"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM signals
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_risk_events(self, limit: int = 50) -> List[Dict]:
        """获取风控事件"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM risk_events
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]


class TelegramNotifier:
    """Telegram 通知器"""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or getattr(config, 'TELEGRAM_BOT_TOKEN', '')
        self.chat_id = chat_id or getattr(config, 'TELEGRAM_CHAT_ID', '')
        self.enabled = getattr(config, 'ENABLE_TELEGRAM', False) and self.bot_token and self.chat_id
        self.logger = get_logger(__name__)
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """发送消息"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                self.logger.warning(f"Telegram 发送失败: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Telegram 发送异常: {e}")
            return False
    
    def notify_trade(
        self,
        action: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        pnl: float = None,
        reason: str = ""
    ):
        """发送交易通知"""
        emoji = {
            'open_long': '🟢 开多',
            'open_short': '🔴 开空',
            'close_long': '📤 平多',
            'close_short': '📤 平空',
            'add_long': '➕ 加多',
            'add_short': '➕ 加空',
            'partial_close_long': '📉 减多',
            'partial_close_short': '📉 减空',
        }.get(f"{action}_{side}", f"{action} {side}")
        
        message = f"<b>{emoji}</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📊 交易对: <code>{symbol}</code>\n"
        message += f"📈 数量: <code>{amount:.6f}</code>\n"
        message += f"💰 价格: <code>{price:.2f}</code>\n"
        
        if pnl is not None:
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            message += f"{pnl_emoji} 盈亏: <code>{pnl:+.2f} USDT</code>\n"
        
        if reason:
            message += f"📝 原因: {reason}\n"
        
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_message(message)
    
    def notify_signal(
        self, 
        strategy: str, 
        signal: str, 
        reason: str,
        strength: float = None,
        confidence: float = None
    ):
        """发送信号通知（增强版）"""
        emoji = {
            'long': '🟢',
            'short': '🔴',
            'close_long': '📤',
            'close_short': '📤',
            'hold': '⏸️',
        }.get(signal, '📊')
        
        message = f"{emoji} <b>策略信号</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📋 策略: {strategy}\n"
        message += f"📊 信号: {signal}\n"
        
        if strength is not None:
            message += f"💪 强度: {strength:.0%}\n"
        if confidence is not None:
            message += f"🎯 置信度: {confidence:.0%}\n"
        
        message += f"📝 原因: {reason}\n"
        message += f"⏰ 时间: {datetime.now().strftime('%H:%M:%S')}"
        
        self.send_message(message)
    
    def notify_risk_event(self, event_type: str, description: str):
        """发送风控事件通知"""
        message = f"⚠️ <b>风控事件</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📋 类型: {event_type}\n"
        message += f"📝 描述: {description}\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_message(message)
    
    def notify_daily_summary(self, stats: Dict):
        """发送每日总结"""
        message = f"📊 <b>每日交易总结</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📈 总交易: {stats.get('total_trades', 0)} 笔\n"
        message += f"✅ 盈利: {stats.get('winning_trades', 0)} 笔\n"
        message += f"❌ 亏损: {stats.get('losing_trades', 0)} 笔\n"
        message += f"📊 胜率: {stats.get('win_rate', 0):.1f}%\n"
        
        pnl = stats.get('total_pnl', 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        message += f"{pnl_emoji} 总盈亏: {pnl:+.2f} USDT\n"
        
        # 新增：盈亏比
        pf = stats.get('profit_factor', 0)
        message += f"📈 盈亏比: {pf:.2f}\n"
        
        message += f"⏰ {datetime.now().strftime('%Y-%m-%d')}"
        
        self.send_message(message)
    
    def notify_error(self, error: str):
        """发送错误通知"""
        message = f"❌ <b>错误通知</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📝 {error}\n"
        message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_message(message)
    
    # ========== 新增通知方法 ==========
    
    def notify_drawdown_warning(self, current_dd: float, max_dd: float):
        """回撤警告"""
        message = f"⚠️ <b>回撤警告</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📉 当前回撤: {current_dd:.1%}\n"
        message += f"📉 最大回撤: {max_dd:.1%}\n"
        message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.send_message(message)
    
    def notify_position_update(
        self,
        side: str,
        amount: float,
        entry_price: float,
        current_price: float,
        unrealized_pnl: float,
        unrealized_pnl_pct: float
    ):
        """持仓更新通知"""
        pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
        side_emoji = "📈" if side == 'long' else "📉"
        
        message = f"{side_emoji} <b>持仓状态</b>\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"方向: {side.upper()}\n"
        message += f"数量: <code>{amount:.6f}</code>\n"
        message += f"开仓价: <code>{entry_price:.2f}</code>\n"
        message += f"当前价: <code>{current_price:.2f}</code>\n"
        message += f"{pnl_emoji} 浮盈: <code>{unrealized_pnl:+.2f} ({unrealized_pnl_pct:+.2f}%)</code>\n"
        message += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        
        self.send_message(message)


class FeishuNotifier:
    """飞书通知器"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or getattr(config, 'FEISHU_WEBHOOK_URL', '')
        self.enabled = getattr(config, 'ENABLE_FEISHU', False) and self.webhook_url
        self.logger = get_logger(__name__)

    def send_message(self, message: str, msg_type: str = "text") -> bool:
        """发送消息"""
        if not self.enabled:
            return False

        try:
            data = {
                "msg_type": msg_type,
                "content": {
                    "text": message
                }
            }

            response = requests.post(self.webhook_url, json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return True
                else:
                    self.logger.warning(f"飞书发送失败: {result}")
                    return False
            else:
                self.logger.warning(f"飞书发送失败: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"飞书发送异常: {e}")
            return False

    def notify_trade(
        self,
        action: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        pnl: float = None,
        reason: str = ""
    ):
        """发送交易通知"""
        emoji = {
            'open_long': '🟢 开多',
            'open_short': '🔴 开空',
            'close_long': '📤 平多',
            'close_short': '📤 平空',
        }.get(f"{action}_{side}", f"{action} {side}")

        message = f"{emoji}\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📊 交易对: {symbol}\n"
        message += f"📈 数量: {amount:.6f}\n"
        message += f"💰 价格: {price:.2f}\n"

        if pnl is not None:
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            message += f"{pnl_emoji} 盈亏: {pnl:+.2f} USDT\n"

        if reason:
            message += f"📝 原因: {reason}\n"

        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self.send_message(message)

    def notify_error(self, error: str):
        """发送错误通知"""
        message = f"❌ 错误通知\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📝 {error}\n"
        message += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self.send_message(message)

    def notify_signal(
        self,
        strategy: str,
        signal: str,
        reason: str,
        strength: float = None,
        confidence: float = None
    ):
        """发送信号通知"""
        emoji = {
            'long': '🟢',
            'short': '🔴',
            'close_long': '📤',
            'close_short': '📤',
            'hold': '⏸️',
        }.get(signal, '📊')

        message = f"{emoji} 策略信号\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📋 策略: {strategy}\n"
        message += f"📊 信号: {signal}\n"

        if strength is not None:
            message += f"💪 强度: {strength:.0%}\n"
        if confidence is not None:
            message += f"🎯 置信度: {confidence:.0%}\n"

        message += f"📝 原因: {reason}\n"
        message += f"⏰ 时间: {datetime.now().strftime('%H:%M:%S')}"

        self.send_message(message)

    def notify_risk_event(self, event_type: str, description: str):
        """发送风控事件通知"""
        message = f"⚠️ 风控事件\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📋 类型: {event_type}\n"
        message += f"📝 描述: {description}\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self.send_message(message)

    def notify_daily_summary(self, stats: Dict):
        """发送每日总结"""
        message = f"📊 每日交易总结\n"
        message += f"━━━━━━━━━━━━━━━\n"
        message += f"📈 总交易: {stats.get('total_trades', 0)} 笔\n"
        message += f"✅ 盈利: {stats.get('winning_trades', 0)} 笔\n"
        message += f"❌ 亏损: {stats.get('losing_trades', 0)} 笔\n"
        message += f"📊 胜率: {stats.get('win_rate', 0):.1f}%\n"

        pnl = stats.get('total_pnl', 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        message += f"{pnl_emoji} 总盈亏: {pnl:+.2f} USDT\n"

        pf = stats.get('profit_factor', 0)
        message += f"📈 盈亏比: {pf:.2f}\n"

        message += f"⏰ {datetime.now().strftime('%Y-%m-%d')}"

        self.send_message(message)


class EmailNotifier:
    """邮件通知器"""

    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = None,
        sender_email: str = None,
        sender_password: str = None,
        receiver_email: str = None
    ):
        self.smtp_server = smtp_server or getattr(config, 'EMAIL_SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = smtp_port or getattr(config, 'EMAIL_SMTP_PORT', 587)
        self.sender_email = sender_email or getattr(config, 'EMAIL_SENDER', '')
        self.sender_password = sender_password or getattr(config, 'EMAIL_PASSWORD', '')
        self.receiver_email = receiver_email or getattr(config, 'EMAIL_RECEIVER', '')
        self.enabled = getattr(config, 'ENABLE_EMAIL', False) and all([
            self.sender_email, self.sender_password, self.receiver_email
        ])
        self.logger = get_logger(__name__)

    def send_message(self, subject: str, body: str, html: bool = True) -> bool:
        """发送邮件"""
        if not self.enabled:
            return False

        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.receiver_email

            # 添加邮件内容
            if html:
                msg.attach(MIMEText(body, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            return True

        except Exception as e:
            self.logger.error(f"邮件发送异常: {e}")
            return False

    def _format_html(self, title: str, content: str, emoji: str = "📊") -> str:
        """格式化HTML邮件"""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                          color: white; padding: 20px; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 10px 10px; }}
                .info-row {{ margin: 10px 0; padding: 10px; background: white; border-radius: 5px; }}
                .label {{ font-weight: bold; color: #667eea; }}
                .footer {{ margin-top: 20px; text-align: center; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>{emoji} {title}</h2>
                </div>
                <div class="content">
                    {content}
                </div>
                <div class="footer">
                    <p>交易机器人自动通知 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def notify_trade(
        self,
        action: str,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        pnl: float = None,
        reason: str = ""
    ):
        """发送交易通知"""
        emoji_map = {
            'open_long': '🟢',
            'open_short': '🔴',
            'close_long': '📤',
            'close_short': '📤',
        }
        emoji = emoji_map.get(f"{action}_{side}", "📊")

        title_map = {
            'open_long': '开多通知',
            'open_short': '开空通知',
            'close_long': '平多通知',
            'close_short': '平空通知',
        }
        title = title_map.get(f"{action}_{side}", "交易通知")

        content = f"""
        <div class="info-row">
            <span class="label">交易对:</span> {symbol}
        </div>
        <div class="info-row">
            <span class="label">方向:</span> {side.upper()}
        </div>
        <div class="info-row">
            <span class="label">数量:</span> {amount:.6f}
        </div>
        <div class="info-row">
            <span class="label">价格:</span> ${price:.2f}
        </div>
        """

        if pnl is not None:
            pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"
            content += f"""
            <div class="info-row" style="background: {pnl_color}20;">
                <span class="label">盈亏:</span>
                <span style="color: {pnl_color}; font-weight: bold;">{pnl:+.2f} USDT</span>
            </div>
            """

        if reason:
            content += f"""
            <div class="info-row">
                <span class="label">原因:</span> {reason}
            </div>
            """

        html = self._format_html(title, content, emoji)
        self.send_message(f"{emoji} {title} - {symbol}", html)

    def notify_error(self, error: str):
        """发送错误通知"""
        content = f"""
        <div class="info-row" style="background: #fee; border-left: 4px solid #f00;">
            <p style="color: #c00; margin: 0;">{error}</p>
        </div>
        """
        html = self._format_html("错误通知", content, "❌")
        self.send_message("❌ 交易机器人错误通知", html)

    def notify_signal(
        self,
        strategy: str,
        signal: str,
        reason: str,
        strength: float = None,
        confidence: float = None
    ):
        """发送信号通知"""
        emoji_map = {
            'long': '🟢',
            'short': '🔴',
            'close_long': '📤',
            'close_short': '📤',
            'hold': '⏸️',
        }
        emoji = emoji_map.get(signal, '📊')

        content = f"""
        <div class="info-row">
            <span class="label">策略:</span> {strategy}
        </div>
        <div class="info-row">
            <span class="label">信号:</span> {signal}
        </div>
        """

        if strength is not None:
            content += f"""
            <div class="info-row">
                <span class="label">强度:</span> {strength:.0%}
            </div>
            """

        if confidence is not None:
            content += f"""
            <div class="info-row">
                <span class="label">置信度:</span> {confidence:.0%}
            </div>
            """

        content += f"""
        <div class="info-row">
            <span class="label">原因:</span> {reason}
        </div>
        """

        html = self._format_html("策略信号", content, emoji)
        self.send_message(f"{emoji} 策略信号 - {strategy}", html)

    def notify_risk_event(self, event_type: str, description: str):
        """发送风控事件通知"""
        content = f"""
        <div class="info-row" style="background: #fff3cd; border-left: 4px solid #ffc107;">
            <div><span class="label">类型:</span> {event_type}</div>
            <div style="margin-top: 10px;"><span class="label">描述:</span> {description}</div>
        </div>
        """
        html = self._format_html("风控事件", content, "⚠️")
        self.send_message("⚠️ 风控事件通知", html)

    def notify_daily_summary(self, stats: Dict):
        """发送每日总结"""
        pnl = stats.get('total_pnl', 0)
        pnl_color = "#22c55e" if pnl >= 0 else "#ef4444"

        content = f"""
        <div class="info-row">
            <span class="label">总交易:</span> {stats.get('total_trades', 0)} 笔
        </div>
        <div class="info-row">
            <span class="label">盈利:</span> {stats.get('winning_trades', 0)} 笔
        </div>
        <div class="info-row">
            <span class="label">亏损:</span> {stats.get('losing_trades', 0)} 笔
        </div>
        <div class="info-row">
            <span class="label">胜率:</span> {stats.get('win_rate', 0):.1f}%
        </div>
        <div class="info-row" style="background: {pnl_color}20;">
            <span class="label">总盈亏:</span>
            <span style="color: {pnl_color}; font-weight: bold; font-size: 18px;">{pnl:+.2f} USDT</span>
        </div>
        <div class="info-row">
            <span class="label">盈亏比:</span> {stats.get('profit_factor', 0):.2f}
        </div>
        """

        html = self._format_html("每日交易总结", content, "📊")
        self.send_message("📊 每日交易总结", html)


class MultiNotifier:
    """多渠道通知器"""

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.feishu = FeishuNotifier()
        self.email = EmailNotifier()
        self.logger = get_logger(__name__)

    def notify_trade(self, *args, **kwargs):
        """发送交易通知到所有渠道"""
        self.telegram.notify_trade(*args, **kwargs)
        self.feishu.notify_trade(*args, **kwargs)
        self.email.notify_trade(*args, **kwargs)

    def notify_error(self, error: str):
        """发送错误通知到所有渠道"""
        self.telegram.notify_error(error)
        self.feishu.notify_error(error)
        self.email.notify_error(error)

    def notify_signal(self, *args, **kwargs):
        """发送信号通知到所有渠道"""
        self.telegram.notify_signal(*args, **kwargs)
        self.feishu.notify_signal(*args, **kwargs)
        self.email.notify_signal(*args, **kwargs)

    def notify_risk_event(self, *args, **kwargs):
        """发送风控事件通知到所有渠道"""
        self.telegram.notify_risk_event(*args, **kwargs)
        self.feishu.notify_risk_event(*args, **kwargs)
        self.email.notify_risk_event(*args, **kwargs)

    def notify_daily_summary(self, *args, **kwargs):
        """发送每日总结到所有渠道"""
        self.telegram.notify_daily_summary(*args, **kwargs)
        self.feishu.notify_daily_summary(*args, **kwargs)
        self.email.notify_daily_summary(*args, **kwargs)


# 全局实例
db = TradeDatabase()
notifier = MultiNotifier()
