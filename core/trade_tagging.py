"""
交易标签系统
记录每笔交易的完整决策链，用于回测和分析
"""
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from utils.logger_utils import get_logger, db

logger = get_logger("trade_tagging")


@dataclass
class TradeTag:
    """交易标签 - 记录完整的决策链"""

    # 基础信息
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 市场状态
    market_regime: str = ""           # ranging/transitioning/trending
    market_confidence: float = 0.0    # 市场状态置信度
    volatility_regime: str = ""       # low/normal/high/extreme
    price: float = 0.0
    volatility: float = 0.0
    atr: float = 0.0
    volume_ratio: float = 0.0

    # 策略信号
    strategy: str = ""
    signal: str = ""                  # long/short/close_long/close_short
    signal_strength: float = 0.0
    signal_confidence: float = 0.0
    signal_reason: str = ""
    signal_indicators: Dict = field(default_factory=dict)

    # 趋势过滤
    trend_filter_enabled: bool = True
    trend_filter_pass: bool = False
    trend_filter_reason: str = ""

    # Claude 分析
    claude_enabled: bool = False
    claude_pass: bool = False
    claude_confidence: float = 0.0
    claude_regime: str = ""
    claude_signal_quality: float = 0.0
    claude_risk_flags: List[str] = field(default_factory=list)
    claude_reason: str = ""
    claude_suggested_sl: float = 0.0
    claude_suggested_tp: float = 0.0

    # 执行层风控
    execution_filter_enabled: bool = False
    execution_filter_pass: bool = False
    execution_filter_reason: str = ""
    spread_check: bool = True
    slippage_check: bool = True
    liquidity_check: bool = True

    # 执行决策
    executed: bool = False
    execution_reason: str = ""
    rejection_stage: str = ""         # trend_filter/claude/execution_filter/risk_manager

    # 仓位信息
    position_size: float = 0.0
    position_size_pct: float = 0.0
    leverage: float = 0.0
    entry_price: float = 0.0
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0

    # 交易结果（平仓后填充）
    exit_price: float = 0.0
    exit_time: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0
    hold_time_minutes: int = 0
    exit_reason: str = ""
    max_favorable_excursion: float = 0.0  # MFE - 最大有利偏移
    max_adverse_excursion: float = 0.0    # MAE - 最大不利偏移

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeTag':
        """从字典创建"""
        return cls(**data)


class TradeTagManager:
    """交易标签管理器"""

    def __init__(self):
        self.current_tag: Optional[TradeTag] = None
        self.tags_history: List[TradeTag] = []
        self._init_database()

    def _init_database(self):
        """初始化数据库表"""
        try:
            # 创建交易标签表
            db.conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_tags (
                    trade_id TEXT PRIMARY KEY,
                    timestamp TEXT,

                    -- 市场状态
                    market_regime TEXT,
                    market_confidence REAL,
                    volatility_regime TEXT,
                    price REAL,
                    volatility REAL,
                    atr REAL,
                    volume_ratio REAL,

                    -- 策略信号
                    strategy TEXT,
                    signal TEXT,
                    signal_strength REAL,
                    signal_confidence REAL,
                    signal_reason TEXT,
                    signal_indicators TEXT,

                    -- 趋势过滤
                    trend_filter_enabled INTEGER,
                    trend_filter_pass INTEGER,
                    trend_filter_reason TEXT,

                    -- Claude 分析
                    claude_enabled INTEGER,
                    claude_pass INTEGER,
                    claude_confidence REAL,
                    claude_regime TEXT,
                    claude_signal_quality REAL,
                    claude_risk_flags TEXT,
                    claude_reason TEXT,
                    claude_suggested_sl REAL,
                    claude_suggested_tp REAL,

                    -- 执行层风控
                    execution_filter_enabled INTEGER,
                    execution_filter_pass INTEGER,
                    execution_filter_reason TEXT,
                    spread_check INTEGER,
                    slippage_check INTEGER,
                    liquidity_check INTEGER,

                    -- 执行决策
                    executed INTEGER,
                    execution_reason TEXT,
                    rejection_stage TEXT,

                    -- 仓位信息
                    position_size REAL,
                    position_size_pct REAL,
                    leverage REAL,
                    entry_price REAL,
                    stop_loss_price REAL,
                    take_profit_price REAL,

                    -- 交易结果
                    exit_price REAL,
                    exit_time TEXT,
                    pnl REAL,
                    pnl_pct REAL,
                    hold_time_minutes INTEGER,
                    exit_reason TEXT,
                    max_favorable_excursion REAL,
                    max_adverse_excursion REAL
                )
            """)
            db.conn.commit()
            logger.info("交易标签表初始化成功")
        except Exception as e:
            logger.error(f"初始化交易标签表失败: {e}")

    def create_tag(
        self,
        strategy: str,
        signal: str,
        signal_strength: float,
        signal_confidence: float,
        signal_reason: str,
        signal_indicators: Dict,
        market_regime: str = "",
        market_confidence: float = 0.0,
        price: float = 0.0,
        volatility: float = 0.0
    ) -> TradeTag:
        """
        创建新的交易标签

        Args:
            strategy: 策略名称
            signal: 信号类型
            signal_strength: 信号强度
            signal_confidence: 信号置信度
            signal_reason: 信号原因
            signal_indicators: 技术指标
            market_regime: 市场状态
            market_confidence: 市场状态置信度
            price: 当前价格
            volatility: 波动率

        Returns:
            TradeTag 对象
        """
        tag = TradeTag(
            strategy=strategy,
            signal=signal,
            signal_strength=signal_strength,
            signal_confidence=signal_confidence,
            signal_reason=signal_reason,
            signal_indicators=signal_indicators,
            market_regime=market_regime,
            market_confidence=market_confidence,
            price=price,
            volatility=volatility
        )

        self.current_tag = tag
        logger.debug(f"创建交易标签: {tag.trade_id}")
        return tag

    def update_trend_filter(
        self,
        passed: bool,
        reason: str
    ):
        """更新趋势过滤结果"""
        if not self.current_tag:
            logger.warning("没有当前交易标签")
            return

        self.current_tag.trend_filter_pass = passed
        self.current_tag.trend_filter_reason = reason

        if not passed:
            self.current_tag.rejection_stage = "trend_filter"

        logger.debug(f"更新趋势过滤: {passed} - {reason}")

    def update_claude_analysis(
        self,
        passed: bool,
        confidence: float,
        regime: str,
        signal_quality: float,
        risk_flags: List[str],
        reason: str,
        suggested_sl: float = 0.0,
        suggested_tp: float = 0.0
    ):
        """更新 Claude 分析结果"""
        if not self.current_tag:
            logger.warning("没有当前交易标签")
            return

        self.current_tag.claude_enabled = True
        self.current_tag.claude_pass = passed
        self.current_tag.claude_confidence = confidence
        self.current_tag.claude_regime = regime
        self.current_tag.claude_signal_quality = signal_quality
        self.current_tag.claude_risk_flags = risk_flags
        self.current_tag.claude_reason = reason
        self.current_tag.claude_suggested_sl = suggested_sl
        self.current_tag.claude_suggested_tp = suggested_tp

        if not passed:
            self.current_tag.rejection_stage = "claude"

        logger.debug(f"更新 Claude 分析: {passed} - {reason}")

    def update_execution_filter(
        self,
        passed: bool,
        reason: str,
        spread_check: bool = True,
        slippage_check: bool = True,
        liquidity_check: bool = True
    ):
        """更新执行层风控结果"""
        if not self.current_tag:
            logger.warning("没有当前交易标签")
            return

        self.current_tag.execution_filter_enabled = True
        self.current_tag.execution_filter_pass = passed
        self.current_tag.execution_filter_reason = reason
        self.current_tag.spread_check = spread_check
        self.current_tag.slippage_check = slippage_check
        self.current_tag.liquidity_check = liquidity_check

        if not passed:
            self.current_tag.rejection_stage = "execution_filter"

        logger.debug(f"更新执行过滤: {passed} - {reason}")

    def mark_executed(
        self,
        executed: bool,
        reason: str,
        position_size: float = 0.0,
        entry_price: float = 0.0,
        stop_loss_price: float = 0.0,
        take_profit_price: float = 0.0
    ):
        """标记为已执行"""
        if not self.current_tag:
            logger.warning("没有当前交易标签")
            return

        self.current_tag.executed = executed
        self.current_tag.execution_reason = reason
        self.current_tag.position_size = position_size
        self.current_tag.entry_price = entry_price
        self.current_tag.stop_loss_price = stop_loss_price
        self.current_tag.take_profit_price = take_profit_price

        logger.debug(f"标记执行: {executed} - {reason}")

    def mark_closed(
        self,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        mfe: float = 0.0,
        mae: float = 0.0
    ):
        """标记为已平仓"""
        if not self.current_tag:
            logger.warning("没有当前交易标签")
            return

        self.current_tag.exit_price = exit_price
        self.current_tag.exit_time = datetime.now().isoformat()
        self.current_tag.pnl = pnl
        self.current_tag.pnl_pct = pnl_pct
        self.current_tag.exit_reason = exit_reason
        self.current_tag.max_favorable_excursion = mfe
        self.current_tag.max_adverse_excursion = mae

        # 计算持仓时间
        entry_time = datetime.fromisoformat(self.current_tag.timestamp)
        exit_time = datetime.fromisoformat(self.current_tag.exit_time)
        self.current_tag.hold_time_minutes = int((exit_time - entry_time).total_seconds() / 60)

        logger.debug(f"标记平仓: PNL={pnl:.2f} ({pnl_pct:.2f}%)")

    def save_tag(self):
        """保存当前标签到数据库"""
        if not self.current_tag:
            logger.warning("没有当前交易标签")
            return

        try:
            tag_dict = self.current_tag.to_dict()

            # 转换布尔值为整数
            for key in ['trend_filter_enabled', 'trend_filter_pass', 'claude_enabled',
                       'claude_pass', 'execution_filter_enabled', 'execution_filter_pass',
                       'spread_check', 'slippage_check', 'liquidity_check', 'executed']:
                if key in tag_dict:
                    tag_dict[key] = int(tag_dict[key])

            # 转换列表和字典为 JSON 字符串
            tag_dict['signal_indicators'] = json.dumps(tag_dict['signal_indicators'])
            tag_dict['claude_risk_flags'] = json.dumps(tag_dict['claude_risk_flags'])

            # 插入数据库
            columns = ', '.join(tag_dict.keys())
            placeholders = ', '.join(['?' for _ in tag_dict])

            db.conn.execute(
                f"INSERT OR REPLACE INTO trade_tags ({columns}) VALUES ({placeholders})",
                list(tag_dict.values())
            )
            db.conn.commit()

            # 添加到历史
            self.tags_history.append(self.current_tag)

            logger.info(f"保存交易标签: {self.current_tag.trade_id}")

            # 清空当前标签
            self.current_tag = None

        except Exception as e:
            logger.error(f"保存交易标签失败: {e}")
            import traceback
            traceback.print_exc()

    def get_tags(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        strategy: Optional[str] = None,
        executed_only: bool = False
    ) -> List[TradeTag]:
        """
        查询交易标签

        Args:
            start_date: 开始日期
            end_date: 结束日期
            strategy: 策略名称
            executed_only: 只返回已执行的

        Returns:
            TradeTag 列表
        """
        try:
            query = "SELECT * FROM trade_tags WHERE 1=1"
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

            if executed_only:
                query += " AND executed = 1"

            query += " ORDER BY timestamp DESC"

            cursor = db.conn.execute(query, params)
            rows = cursor.fetchall()

            tags = []
            for row in rows:
                tag_dict = dict(row)

                # 转换整数为布尔值
                for key in ['trend_filter_enabled', 'trend_filter_pass', 'claude_enabled',
                           'claude_pass', 'execution_filter_enabled', 'execution_filter_pass',
                           'spread_check', 'slippage_check', 'liquidity_check', 'executed']:
                    if key in tag_dict:
                        tag_dict[key] = bool(tag_dict[key])

                # 转换 JSON 字符串为列表和字典
                if tag_dict.get('signal_indicators'):
                    tag_dict['signal_indicators'] = json.loads(tag_dict['signal_indicators'])
                if tag_dict.get('claude_risk_flags'):
                    tag_dict['claude_risk_flags'] = json.loads(tag_dict['claude_risk_flags'])

                tags.append(TradeTag.from_dict(tag_dict))

            return tags

        except Exception as e:
            logger.error(f"查询交易标签失败: {e}")
            return []

    def get_rejection_stats(self) -> Dict:
        """获取拒绝统计"""
        try:
            cursor = db.conn.execute("""
                SELECT
                    rejection_stage,
                    COUNT(*) as count
                FROM trade_tags
                WHERE executed = 0 AND rejection_stage != ''
                GROUP BY rejection_stage
            """)

            stats = {}
            for row in cursor.fetchall():
                stats[row['rejection_stage']] = row['count']

            return stats

        except Exception as e:
            logger.error(f"获取拒绝统计失败: {e}")
            return {}

    def get_claude_accuracy(self) -> Dict:
        """
        计算 Claude 的准确率

        返回：
        - claude_reject_correct: Claude 拒绝且实际会亏损的比例
        - claude_accept_correct: Claude 通过且实际盈利的比例
        """
        try:
            # Claude 拒绝的信号
            cursor = db.conn.execute("""
                SELECT COUNT(*) as total
                FROM trade_tags
                WHERE claude_enabled = 1 AND claude_pass = 0
            """)
            claude_rejects = cursor.fetchone()['total']

            # Claude 通过且执行的信号
            cursor = db.conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
                FROM trade_tags
                WHERE claude_enabled = 1 AND claude_pass = 1 AND executed = 1 AND pnl != 0
            """)
            row = cursor.fetchone()
            claude_accepts = row['total']
            claude_wins = row['wins']

            return {
                'claude_rejects': claude_rejects,
                'claude_accepts': claude_accepts,
                'claude_wins': claude_wins,
                'claude_win_rate': claude_wins / claude_accepts if claude_accepts > 0 else 0
            }

        except Exception as e:
            logger.error(f"计算 Claude 准确率失败: {e}")
            return {}


# 全局实例
_tag_manager: Optional[TradeTagManager] = None


def get_tag_manager() -> TradeTagManager:
    """获取交易标签管理器单例"""
    global _tag_manager
    if _tag_manager is None:
        _tag_manager = TradeTagManager()
    return _tag_manager
