"""
日志和数据库工具 - 增强版
"""
import logging
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import os
import requests

import config

# 创建日志目录
LOG_DIR = getattr(config, 'LOG_DIR', 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def get_logger(name: str) -> logging.Logger:
    """获取 logger 实例"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # 从 config 获取日志级别，兼容旧配置
        log_level = getattr(config, 'LOG_LEVEL', 'INFO')
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # 控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        
        # 文件输出 - 兼容不同配置名
        log_file = getattr(config, 'LOG_FILE', 'trading_bot.log')
        file_handler = logging.FileHandler(
            os.path.join(LOG_DIR, log_file),
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
        return sqlite3.connect(self.db_file)
    
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
        status: str = "filled"
    ) -> int:
        """记录交易（参数顺序调整，order_id 改为可选）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 自动计算 value_usdt
        if value_usdt == 0:
            value_usdt = amount * price
        
        cursor.execute('''
            INSERT INTO trades (
                order_id, symbol, side, action, amount, price,
                value_usdt, pnl, pnl_percent, strategy, reason, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id, symbol, side, action, amount, price,
            value_usdt, pnl, pnl_percent, strategy, reason, status
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
        
        indicators_json = json.dumps(indicators or {})
        
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
        leverage: int
    ):
        """记录持仓快照"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO position_snapshots (
                symbol, side, amount, entry_price, current_price,
                unrealized_pnl, leverage
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, side, amount, entry_price, current_price, unrealized_pnl, leverage))
        
        conn.commit()
        conn.close()
    
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


# 全局实例
db = TradeDatabase()
notifier = TelegramNotifier()
