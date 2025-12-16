"""
影子模式（Shadow Mode）
全流程跑完但不下单，记录每个阶段的决策，用于A/B对比
"""
from typing import Dict, Optional, Tuple
from datetime import datetime
import pandas as pd

import config
from logger_utils import get_logger, db
from strategies import Signal, TradeSignal

logger = get_logger("shadow_mode")


class ShadowModeTracker:
    """影子模式追踪器"""

    def __init__(self):
        self.enabled = getattr(config, 'ENABLE_SHADOW_MODE', False)
        self._init_database()

    def _init_database(self):
        """初始化影子模式数据表"""
        try:
            conn = db._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shadow_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    trade_id TEXT,

                    -- 市场状态
                    price REAL,
                    market_regime TEXT,
                    volatility REAL,

                    -- 策略信号
                    strategy TEXT,
                    signal TEXT,
                    signal_strength REAL,
                    signal_confidence REAL,

                    -- 各阶段决策（would_execute_xxx）
                    would_execute_strategy INTEGER,      -- 策略是否生成信号
                    would_execute_after_trend INTEGER,   -- 趋势过滤后是否执行
                    would_execute_after_claude INTEGER,  -- Claude分析后是否执行
                    would_execute_after_exec INTEGER,    -- 执行层风控后是否执行
                    final_would_execute INTEGER,         -- 最终是否执行

                    -- 拒绝原因
                    rejection_stage TEXT,
                    rejection_reason TEXT,

                    -- 趋势过滤详情
                    trend_filter_pass INTEGER,
                    trend_filter_reason TEXT,

                    -- Claude详情
                    claude_enabled INTEGER,
                    claude_pass INTEGER,
                    claude_confidence REAL,
                    claude_regime TEXT,
                    claude_signal_quality REAL,
                    claude_risk_flags TEXT,

                    -- 执行层风控详情
                    exec_filter_pass INTEGER,
                    exec_filter_reason TEXT,
                    spread_pct REAL,
                    volume_ratio REAL,
                    atr_spike_ratio REAL,

                    -- 仓位计算
                    base_position_pct REAL,
                    adjusted_position_pct REAL,
                    position_adjustment_factor REAL,

                    -- 实际执行（如果不是影子模式）
                    actually_executed INTEGER,
                    actual_entry_price REAL,
                    actual_exit_price REAL,
                    actual_pnl REAL,
                    actual_pnl_pct REAL
                )
            """)

            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_shadow_timestamp
                ON shadow_decisions(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_shadow_trade_id
                ON shadow_decisions(trade_id)
            """)

            conn.commit()
            conn.close()
            logger.info("影子模式数据表初始化成功")
        except Exception as e:
            logger.error(f"初始化影子模式数据表失败: {e}")

    def record_decision(
        self,
        trade_id: str,
        price: float,
        market_regime: str,
        volatility: float,
        signal: TradeSignal,

        # 各阶段决策
        would_execute_strategy: bool,
        would_execute_after_trend: bool,
        would_execute_after_claude: bool,
        would_execute_after_exec: bool,
        final_would_execute: bool,

        # 拒绝信息
        rejection_stage: str = "",
        rejection_reason: str = "",

        # 详细信息
        trend_details: Optional[Dict] = None,
        claude_details: Optional[Dict] = None,
        exec_details: Optional[Dict] = None,
        position_details: Optional[Dict] = None,

        # 实际执行（如果不是影子模式）
        actually_executed: bool = False,
        actual_entry_price: float = 0.0
    ):
        """
        记录决策过程

        Args:
            trade_id: 交易ID
            price: 当前价格
            market_regime: 市场状态
            volatility: 波动率
            signal: 策略信号
            would_execute_strategy: 策略是否生成信号
            would_execute_after_trend: 趋势过滤后是否执行
            would_execute_after_claude: Claude后是否执行
            would_execute_after_exec: 执行层风控后是否执行
            final_would_execute: 最终是否执行
            rejection_stage: 拒绝阶段
            rejection_reason: 拒绝原因
            trend_details: 趋势过滤详情
            claude_details: Claude详情
            exec_details: 执行层风控详情
            position_details: 仓位详情
            actually_executed: 是否实际执行
            actual_entry_price: 实际入场价
        """
        if not self.enabled:
            return

        try:
            # 提取详情
            trend_details = trend_details or {}
            claude_details = claude_details or {}
            exec_details = exec_details or {}
            position_details = position_details or {}

            data = {
                'timestamp': datetime.now().isoformat(),
                'trade_id': trade_id,
                'price': price,
                'market_regime': market_regime,
                'volatility': volatility,

                'strategy': signal.strategy,
                'signal': signal.signal.value,
                'signal_strength': signal.strength,
                'signal_confidence': signal.confidence,

                'would_execute_strategy': int(would_execute_strategy),
                'would_execute_after_trend': int(would_execute_after_trend),
                'would_execute_after_claude': int(would_execute_after_claude),
                'would_execute_after_exec': int(would_execute_after_exec),
                'final_would_execute': int(final_would_execute),

                'rejection_stage': rejection_stage,
                'rejection_reason': rejection_reason,

                'trend_filter_pass': int(trend_details.get('pass', False)),
                'trend_filter_reason': trend_details.get('reason', ''),

                'claude_enabled': int(claude_details.get('enabled', False)),
                'claude_pass': int(claude_details.get('pass', False)),
                'claude_confidence': claude_details.get('confidence', 0.0),
                'claude_regime': claude_details.get('regime', ''),
                'claude_signal_quality': claude_details.get('signal_quality', 0.0),
                'claude_risk_flags': str(claude_details.get('risk_flags', [])),

                'exec_filter_pass': int(exec_details.get('pass', False)),
                'exec_filter_reason': exec_details.get('reason', ''),
                'spread_pct': exec_details.get('spread_pct', 0.0),
                'volume_ratio': exec_details.get('volume_ratio', 0.0),
                'atr_spike_ratio': exec_details.get('atr_spike_ratio', 0.0),

                'base_position_pct': position_details.get('base_pct', 0.0),
                'adjusted_position_pct': position_details.get('adjusted_pct', 0.0),
                'position_adjustment_factor': position_details.get('adjustment_factor', 1.0),

                'actually_executed': int(actually_executed),
                'actual_entry_price': actual_entry_price,
                'actual_exit_price': 0.0,
                'actual_pnl': 0.0,
                'actual_pnl_pct': 0.0,
            }

            # 插入数据库
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])

            conn = db._get_conn()
            conn.execute(
                f"INSERT INTO shadow_decisions ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            conn.commit()
            conn.close()

            logger.debug(f"影子模式记录: {trade_id} - 最终决策: {final_would_execute}")

        except Exception as e:
            logger.error(f"记录影子模式决策失败: {e}")
            import traceback
            traceback.print_exc()

    def update_actual_result(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        pnl_pct: float
    ):
        """
        更新实际交易结果

        Args:
            trade_id: 交易ID
            exit_price: 平仓价格
            pnl: 盈亏
            pnl_pct: 盈亏百分比
        """
        if not self.enabled:
            return

        try:
            conn = db._get_conn()
            conn.execute("""
                UPDATE shadow_decisions
                SET actual_exit_price = ?,
                    actual_pnl = ?,
                    actual_pnl_pct = ?
                WHERE trade_id = ?
            """, (exit_price, pnl, pnl_pct, trade_id))
            conn.commit()
            conn.close()

            logger.debug(f"更新影子模式结果: {trade_id} - PNL: {pnl:.2f}")

        except Exception as e:
            logger.error(f"更新影子模式结果失败: {e}")

    def get_ab_comparison(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        获取A/B对比数据

        对比：
        - 只策略（would_execute_strategy）
        - 策略+趋势过滤（would_execute_after_trend）
        - 策略+趋势+Claude（would_execute_after_claude）
        - 策略+趋势+Claude+执行层（final_would_execute）

        Returns:
            对比统计数据
        """
        try:
            query = "SELECT * FROM shadow_decisions WHERE 1=1"
            params = []

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)

            conn = db._get_conn()
            import sqlite3
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {}

            # 统计各阶段
            stats = {
                'total_signals': len(rows),
                'strategy_only': {
                    'would_execute': sum(1 for r in rows if r['would_execute_strategy']),
                    'rejection_rate': 0.0,
                },
                'after_trend_filter': {
                    'would_execute': sum(1 for r in rows if r['would_execute_after_trend']),
                    'rejection_rate': 0.0,
                    'rejected_by_trend': sum(1 for r in rows if r['would_execute_strategy'] and not r['would_execute_after_trend']),
                },
                'after_claude': {
                    'would_execute': sum(1 for r in rows if r['would_execute_after_claude']),
                    'rejection_rate': 0.0,
                    'rejected_by_claude': sum(1 for r in rows if r['would_execute_after_trend'] and not r['would_execute_after_claude']),
                },
                'after_exec_filter': {
                    'would_execute': sum(1 for r in rows if r['final_would_execute']),
                    'rejection_rate': 0.0,
                    'rejected_by_exec': sum(1 for r in rows if r['would_execute_after_claude'] and not r['final_would_execute']),
                },
            }

            # 计算拒绝率
            total = stats['total_signals']
            if total > 0:
                stats['strategy_only']['rejection_rate'] = 0.0
                stats['after_trend_filter']['rejection_rate'] = (total - stats['after_trend_filter']['would_execute']) / total
                stats['after_claude']['rejection_rate'] = (total - stats['after_claude']['would_execute']) / total
                stats['after_exec_filter']['rejection_rate'] = (total - stats['after_exec_filter']['would_execute']) / total

            return stats

        except Exception as e:
            logger.error(f"获取A/B对比失败: {e}")
            return {}

    def get_rejection_breakdown(self) -> Dict:
        """获取拒绝原因分解"""
        try:
            conn = db._get_conn()
            import sqlite3
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT
                    rejection_stage,
                    COUNT(*) as count,
                    AVG(signal_strength) as avg_signal_strength,
                    AVG(claude_confidence) as avg_claude_confidence
                FROM shadow_decisions
                WHERE rejection_stage != ''
                GROUP BY rejection_stage
            """)

            breakdown = {}
            for row in cursor.fetchall():
                breakdown[row['rejection_stage']] = {
                    'count': row['count'],
                    'avg_signal_strength': row['avg_signal_strength'] or 0,
                    'avg_claude_confidence': row['avg_claude_confidence'] or 0,
                }

            conn.close()
            return breakdown

        except Exception as e:
            logger.error(f"获取拒绝分解失败: {e}")
            return {}


# 全局实例
_shadow_tracker: Optional[ShadowModeTracker] = None


def get_shadow_tracker() -> ShadowModeTracker:
    """获取影子模式追踪器单例"""
    global _shadow_tracker
    if _shadow_tracker is None:
        _shadow_tracker = ShadowModeTracker()
    return _shadow_tracker
