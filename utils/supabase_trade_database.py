"""
Supabase 实时交易数据库实现

与 TradeDatabase 接口完全兼容，支持配置切换。
"""
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from backtest.adapters.storage.supabase_client import get_supabase_client
from utils.logger_utils import get_logger

try:
    import config
except ImportError:
    config = None

_logger = get_logger("supabase.trade_db")


class SupabaseTradeDatabase:
    """Supabase 交易记录数据库（与 TradeDatabase 接口兼容）"""

    # 表名映射（添加 live_ 前缀）
    TABLE_TRADES = "live_trades"
    TABLE_SIGNALS = "live_signals"
    TABLE_POSITION_SNAPSHOTS = "live_position_snapshots"
    TABLE_BALANCE_SNAPSHOTS = "live_balance_snapshots"
    TABLE_RISK_EVENTS = "live_risk_events"

    def __init__(self):
        self._client = get_supabase_client()
        # 批量写入缓冲区
        self._trade_buffer: List[Dict[str, Any]] = []
        self._signal_buffer: List[Dict[str, Any]] = []
        self._last_trade_flush = time.time()
        self._last_signal_flush = time.time()
        self._batch_size = max(1, int(getattr(config, 'SUPABASE_BATCH_SIZE', 100)))
        self._batch_flush_interval = float(getattr(config, 'SUPABASE_BATCH_FLUSH_INTERVAL', 5))
        self._max_retries = 3
        _logger.info("SupabaseTradeDatabase initialized, batch_size=%d", self._batch_size)

    def _get_timestamp_ms(self) -> int:
        """获取毫秒时间戳"""
        return int(time.time() * 1000)

    def _write_with_retry(self, operation, description: str = "write"):
        """指数退避重试"""
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return operation()
            except Exception as e:
                last_error = e
                if attempt == self._max_retries - 1:
                    _logger.error("Supabase %s failed after %d retries: %s",
                                  description, self._max_retries, e)
                    raise
                wait_time = 2 ** attempt
                _logger.warning("Supabase %s failed (attempt %d/%d), retrying in %ds: %s",
                                description, attempt + 1, self._max_retries, wait_time, e)
                time.sleep(wait_time)
        raise last_error

    @staticmethod
    def _convert_numpy_types(obj):
        """递归转换 numpy 类型为 Python 原生类型"""
        if obj is None:
            return None
        elif isinstance(obj, dict):
            return {k: SupabaseTradeDatabase._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [SupabaseTradeDatabase._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif hasattr(obj, 'item') and hasattr(obj, 'dtype'):
            return obj.item()
        else:
            return obj

    # ==================== 交易记录方法 ====================

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
        filled_price: float = None,
        filled_time: str = None,
        fee: float = None,
        fee_currency: str = None,
        batch_number: int = None,
        remaining_amount: float = None,
        leverage: int = None,
        margin_mode: str = None,
        position_side: str = None,
        order_type: str = None,
        reduce_only: bool = None,
        trade_side: str = None
    ) -> int:
        """记录交易（P2增强：支持 Bitget API 详细信息）"""
        if value_usdt == 0:
            value_usdt = amount * price

        data = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "action": action,
            "amount": amount,
            "price": price,
            "value_usdt": value_usdt,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "strategy": strategy,
            "reason": reason,
            "status": status,
            "filled_price": filled_price,
            "filled_time": filled_time,
            "fee": fee,
            "fee_currency": fee_currency,
            "batch_number": batch_number,
            "remaining_amount": remaining_amount,
            "leverage": leverage,
            "margin_mode": margin_mode,
            "position_side": position_side,
            "order_type": order_type,
            "reduce_only": reduce_only,
            "trade_side": trade_side,
            "created_at": self._get_timestamp_ms()
        }

        def _insert():
            result = self._client.table(self.TABLE_TRADES).insert(data).execute()
            return result.data[0]["id"] if result.data else 0

        return self._write_with_retry(_insert, "log_trade")

    def log_trade_buffered(
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
        filled_price: float = None,
        filled_time: str = None,
        fee: float = None,
        fee_currency: str = None,
        batch_number: int = None,
        remaining_amount: float = None,
        leverage: int = None,
        margin_mode: str = None,
        position_side: str = None,
        order_type: str = None,
        reduce_only: bool = None,
        trade_side: str = None
    ) -> Optional[int]:
        """缓冲交易记录（P2增强：支持 Bitget API 详细信息）"""
        if not getattr(config, 'DB_BATCH_WRITES_ENABLED', False):
            return self.log_trade(
                symbol=symbol, side=side, action=action, amount=amount, price=price,
                order_id=order_id, value_usdt=value_usdt, pnl=pnl, pnl_percent=pnl_percent,
                strategy=strategy, reason=reason, status=status,
                filled_price=filled_price, filled_time=filled_time,
                fee=fee, fee_currency=fee_currency,
                batch_number=batch_number, remaining_amount=remaining_amount,
                leverage=leverage, margin_mode=margin_mode, position_side=position_side,
                order_type=order_type, reduce_only=reduce_only, trade_side=trade_side
            )

        if value_usdt == 0:
            value_usdt = amount * price

        trade_data = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "action": action,
            "amount": amount,
            "price": price,
            "value_usdt": value_usdt,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "strategy": strategy,
            "reason": reason,
            "status": status,
            "filled_price": filled_price,
            "filled_time": filled_time,
            "fee": fee,
            "fee_currency": fee_currency,
            "batch_number": batch_number,
            "remaining_amount": remaining_amount,
            "leverage": leverage,
            "margin_mode": margin_mode,
            "position_side": position_side,
            "order_type": order_type,
            "reduce_only": reduce_only,
            "trade_side": trade_side,
            "created_at": self._get_timestamp_ms()
        }

        self._trade_buffer.append(trade_data)

        if len(self._trade_buffer) >= self._batch_size:
            self._flush_trade_buffer(force=True)
        elif time.time() - self._last_trade_flush >= self._batch_flush_interval:
            self._flush_trade_buffer(force=True)

        return None

    def log_trades_batch(self, trades_list: List[Dict[str, Any]]) -> int:
        """批量写入交易记录"""
        if not trades_list:
            return 0

        # 添加时间戳
        ts = self._get_timestamp_ms()
        for trade in trades_list:
            if "created_at" not in trade:
                trade["created_at"] = ts

        def _insert():
            result = self._client.table(self.TABLE_TRADES).insert(trades_list).execute()
            return len(result.data) if result.data else 0

        return self._write_with_retry(_insert, "log_trades_batch")

    def _flush_trade_buffer(self, force: bool = False) -> int:
        """刷新交易缓冲区"""
        if not force:
            if len(self._trade_buffer) < self._batch_size:
                elapsed = time.time() - self._last_trade_flush
                if elapsed < self._batch_flush_interval:
                    return 0

        if not self._trade_buffer:
            return 0

        count = self.log_trades_batch(self._trade_buffer)
        self._trade_buffer.clear()
        self._last_trade_flush = time.time()
        return count

    # ==================== 信号记录方法 ====================

    def log_signal(
        self,
        strategy: str,
        signal: str,
        reason: str,
        strength: float = 1.0,
        confidence: float = 1.0,
        indicators: Dict = None
    ) -> int:
        """记录策略信号"""
        strength = float(strength) if strength is not None else 1.0
        confidence = float(confidence) if confidence is not None else 1.0
        indicators_clean = self._convert_numpy_types(indicators or {})

        data = {
            "strategy": strategy,
            "signal": signal,
            "reason": reason,
            "strength": strength,
            "confidence": confidence,
            "indicators": indicators_clean,
            "created_at": self._get_timestamp_ms()
        }

        def _insert():
            result = self._client.table(self.TABLE_SIGNALS).insert(data).execute()
            return result.data[0]["id"] if result.data else 0

        return self._write_with_retry(_insert, "log_signal")

    def log_signal_buffered(
        self,
        strategy: str,
        signal: str,
        reason: str,
        strength: float = 1.0,
        confidence: float = 1.0,
        indicators: Dict = None
    ) -> Optional[int]:
        """缓冲信号记录"""
        if not getattr(config, 'DB_BATCH_WRITES_ENABLED', False):
            return self.log_signal(
                strategy=strategy, signal=signal, reason=reason,
                strength=strength, confidence=confidence, indicators=indicators
            )

        strength = float(strength) if strength is not None else 1.0
        confidence = float(confidence) if confidence is not None else 1.0
        indicators_clean = self._convert_numpy_types(indicators or {})

        signal_data = {
            "strategy": strategy,
            "signal": signal,
            "reason": reason,
            "strength": strength,
            "confidence": confidence,
            "indicators": indicators_clean,
            "created_at": self._get_timestamp_ms()
        }

        self._signal_buffer.append(signal_data)

        if len(self._signal_buffer) >= self._batch_size:
            self._flush_signal_buffer(force=True)
        elif time.time() - self._last_signal_flush >= self._batch_flush_interval:
            self._flush_signal_buffer(force=True)

        return None

    def log_signals_batch(self, signals_list: List[Dict[str, Any]]) -> int:
        """批量写入信号记录"""
        if not signals_list:
            return 0

        ts = self._get_timestamp_ms()
        for sig in signals_list:
            if "created_at" not in sig:
                sig["created_at"] = ts
            # 确保 indicators 是 dict 而非 JSON 字符串
            if isinstance(sig.get("indicators"), str):
                try:
                    sig["indicators"] = json.loads(sig["indicators"])
                except (json.JSONDecodeError, TypeError):
                    sig["indicators"] = {}

        def _insert():
            result = self._client.table(self.TABLE_SIGNALS).insert(signals_list).execute()
            return len(result.data) if result.data else 0

        return self._write_with_retry(_insert, "log_signals_batch")

    def _flush_signal_buffer(self, force: bool = False) -> int:
        """刷新信号缓冲区"""
        if not force:
            if len(self._signal_buffer) < self._batch_size:
                elapsed = time.time() - self._last_signal_flush
                if elapsed < self._batch_flush_interval:
                    return 0

        if not self._signal_buffer:
            return 0

        count = self.log_signals_batch(self._signal_buffer)
        self._signal_buffer.clear()
        self._last_signal_flush = time.time()
        return count

    def flush_buffers(self, force: bool = False) -> None:
        """刷新所有缓冲区"""
        self._flush_trade_buffer(force=force)
        self._flush_signal_buffer(force=force)

    # ==================== 持仓快照方法 ====================

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
        entry_time: str = None,
        margin_mode: str = None,
        liquidation_price: float = None,
        margin_ratio: float = None,
        mark_price: float = None,
        notional: float = None,
        initial_margin: float = None,
        maintenance_margin: float = None
    ):
        """记录持仓快照（P2增强：支持 Bitget API 详细信息）"""
        data = {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "entry_price": entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "leverage": leverage,
            "highest_price": highest_price,
            "lowest_price": lowest_price,
            "entry_time": int(entry_time) if entry_time else None,
            "margin_mode": margin_mode,
            "liquidation_price": liquidation_price,
            "margin_ratio": margin_ratio,
            "mark_price": mark_price,
            "notional": notional,
            "initial_margin": initial_margin,
            "maintenance_margin": maintenance_margin,
            "created_at": self._get_timestamp_ms()
        }

        def _insert():
            self._client.table(self.TABLE_POSITION_SNAPSHOTS).insert(data).execute()

        self._write_with_retry(_insert, "log_position_snapshot")

    def get_latest_position_snapshot(self, symbol: str) -> Optional[Dict]:
        """获取最新的持仓快照"""
        result = (
            self._client.table(self.TABLE_POSITION_SNAPSHOTS)
            .select("*")
            .eq("symbol", symbol)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            row = result.data[0]
            return {
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "amount": row.get("amount"),
                "entry_price": row.get("entry_price"),
                "current_price": row.get("current_price"),
                "unrealized_pnl": row.get("unrealized_pnl"),
                "leverage": row.get("leverage"),
                "highest_price": row.get("highest_price") or 0,
                "lowest_price": row.get("lowest_price") or 0,
                "entry_time": row.get("entry_time"),
                "created_at": row.get("created_at")
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
        query = self._client.table(self.TABLE_POSITION_SNAPSHOTS).select("*")

        if symbol:
            query = query.eq("symbol", symbol)

        # 日期过滤（转换为毫秒时间戳）
        if start_date:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
            query = query.gte("created_at", start_ts)

        if end_date:
            end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000) + 86400000
            query = query.lt("created_at", end_ts)

        result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return result.data if result.data else []

    # ==================== 余额快照方法 ====================

    def log_balance_snapshot(self, total: float, free: float, used: float):
        """记录余额快照"""
        data = {
            "total": total,
            "free": free,
            "used": used,
            "created_at": self._get_timestamp_ms()
        }

        def _insert():
            self._client.table(self.TABLE_BALANCE_SNAPSHOTS).insert(data).execute()

        self._write_with_retry(_insert, "log_balance_snapshot")

    # ==================== 风控事件方法 ====================

    def log_risk_event(
        self,
        event_type: str,
        description: str,
        current_price: float = 0,
        trigger_price: float = 0,
        position_side: str = ""
    ):
        """记录风控事件"""
        data = {
            "event_type": event_type,
            "description": description,
            "current_price": current_price,
            "trigger_price": trigger_price,
            "position_side": position_side,
            "created_at": self._get_timestamp_ms()
        }

        def _insert():
            self._client.table(self.TABLE_RISK_EVENTS).insert(data).execute()

        self._write_with_retry(_insert, "log_risk_event")

    # ==================== 交易查询方法 ====================

    def get_trades(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取交易记录"""
        result = (
            self._client.table(self.TABLE_TRADES)
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data if result.data else []

    def get_trade_by_id(self, trade_id: int) -> Optional[Dict]:
        """根据 ID 获取单个交易详情"""
        result = (
            self._client.table(self.TABLE_TRADES)
            .select("*")
            .eq("id", trade_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_today_trades(self) -> List[Dict]:
        """获取今日交易"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_ts = int(today_start.timestamp() * 1000)

        result = (
            self._client.table(self.TABLE_TRADES)
            .select("*")
            .gte("created_at", today_start_ts)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data if result.data else []

    def get_today_pnl(self) -> float:
        """获取今日盈亏"""
        trades = self.get_today_trades()
        return sum(t.get("pnl", 0) or 0 for t in trades)

    def get_statistics(self, days: int = 30) -> Dict:
        """获取统计数据"""
        # 总交易次数
        all_trades = self._client.table(self.TABLE_TRADES).select("id", count="exact").execute()
        total_trades = all_trades.count if hasattr(all_trades, 'count') else len(all_trades.data or [])

        # 近 N 天交易
        cutoff_ts = int((datetime.now().timestamp() - days * 86400) * 1000)
        recent_result = (
            self._client.table(self.TABLE_TRADES)
            .select("pnl")
            .gte("created_at", cutoff_ts)
            .execute()
        )
        recent_trades = recent_result.data or []

        total_pnl = sum(t.get("pnl", 0) or 0 for t in recent_trades)
        winning = [t for t in recent_trades if (t.get("pnl") or 0) > 0]
        losing = [t for t in recent_trades if (t.get("pnl") or 0) < 0]

        win_rate = len(winning) / len(recent_trades) * 100 if recent_trades else 0

        return {
            "total_trades": total_trades,
            "recent_trades": len(recent_trades),
            "total_pnl": total_pnl,
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate
        }

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """获取最近交易（兼容方法）"""
        return self.get_trades(limit=limit)
