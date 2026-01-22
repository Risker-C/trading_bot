"""
Supabase Backtest Repository - Cloud persistence layer
"""
import hashlib
import json
import time
import uuid
import zlib
from datetime import datetime
from typing import Dict, List, Any, Iterable, Optional

import pandas as pd

from backtest.domain.interfaces import IDataRepository
from backtest.adapters.storage.supabase_client import get_supabase_client
from backtest.adapters.storage.batch_writer import BatchWriter
from utils.logger_utils import get_logger


def _encode_bytea(data: bytes) -> str:
    if not data:
        return "\\x"
    return "\\x" + data.hex()


def _decode_bytea(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        if value.startswith("\\x") or value.startswith("\\X"):
            return bytes.fromhex(value[2:])
        try:
            return bytes.fromhex(value)
        except ValueError:
            return value.encode()
    raise TypeError(f"Unsupported bytea value type: {type(value)}")


def _stable_kline_id(session_id: str, ts: int) -> int:
    payload = f"{session_id}:{ts}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    value = int.from_bytes(digest, "big", signed=False)
    value &= (1 << 62) - 1
    return value | (1 << 62)


def _stable_trade_id(session_id: str, trade: Dict) -> int:
    parts = [
        session_id,
        str(trade.get("ts", "")),
        str(trade.get("action", "")),
        str(trade.get("side", "")),
        str(trade.get("symbol", "")),
        repr(trade.get("qty", "")),
        repr(trade.get("price", "")),
        repr(trade.get("open_trade_id", "")),
    ]
    payload = "|".join(parts).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    value = int.from_bytes(digest, "big", signed=False)
    value &= (1 << 62) - 1
    return value | (1 << 62)

_logger = get_logger("supabase.repo")


class SupabaseRepository(IDataRepository):
    """Supabase storage adapter for optimization/backtest runs"""

    def __init__(self):
        self.client = get_supabase_client()

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> pd.DataFrame:
        start = time.monotonic()
        try:
            response = self.client.table('kline_datasets') \
                .select('data') \
                .eq('symbol', symbol) \
                .eq('timeframe', timeframe) \
                .lte('start_ts', start_ts) \
                .gte('end_ts', end_ts) \
                .order('created_at', desc=True) \
                .limit(1) \
                .execute()
        except Exception:
            _logger.exception(
                "Supabase get_candles failed symbol=%s timeframe=%s start_ts=%s end_ts=%s",
                symbol,
                timeframe,
                start_ts,
                end_ts
            )
            raise

        if not response.data:
            _logger.debug(
                "Supabase get_candles empty symbol=%s timeframe=%s elapsed=%.3fs",
                symbol,
                timeframe,
                time.monotonic() - start
            )
            return pd.DataFrame()

        compressed_data = _decode_bytea(response.data[0].get('data'))
        if not compressed_data:
            _logger.warning(
                "Supabase get_candles empty data symbol=%s timeframe=%s",
                symbol,
                timeframe
            )
            return pd.DataFrame()

        json_data = zlib.decompress(compressed_data).decode()
        klines = json.loads(json_data)

        df = pd.DataFrame(klines)
        if df.empty:
            return df
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        _logger.debug(
            "Supabase get_candles ok rows=%s elapsed=%.3fs",
            len(df),
            time.monotonic() - start
        )
        return df

    async def save_kline_dataset(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        data: bytes
    ) -> str:
        dataset_id = str(uuid.uuid4())
        checksum = str(hash(data))
        now = int(datetime.utcnow().timestamp())

        payload = {
            'id': dataset_id,
            'symbol': symbol,
            'timeframe': timeframe,
            'start_ts': start_ts,
            'end_ts': end_ts,
            'checksum': checksum,
            'data': _encode_bytea(data),
            'created_at': now
        }

        start = time.monotonic()
        try:
            self.client.table('kline_datasets') \
                .upsert(payload, on_conflict='symbol,timeframe,start_ts,end_ts') \
                .execute()
        except Exception:
            _logger.exception(
                "Supabase save_kline_dataset failed symbol=%s timeframe=%s start_ts=%s end_ts=%s",
                symbol,
                timeframe,
                start_ts,
                end_ts
            )
            raise

        _logger.info(
            "Supabase save_kline_dataset ok id=%s size=%s elapsed=%.3fs",
            dataset_id,
            len(data),
            time.monotonic() - start
        )

        return dataset_id

    async def create_backtest_run(self, params: Dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        payload = {
            'id': run_id,
            'kline_dataset_id': params['kline_dataset_id'],
            'strategy_version_id': params['strategy_version_id'],
            'param_set_id': params.get('param_set_id'),
            'filter_set': json.dumps(params.get('filter_set', {})),
            'status': 'created',
            'created_at': now
        }

        start = time.monotonic()
        try:
            self.client.table('backtest_runs').insert(payload).execute()
        except Exception:
            _logger.exception("Supabase create_backtest_run failed id=%s", run_id)
            raise
        _logger.info(
            "Supabase create_backtest_run ok id=%s elapsed=%.3fs",
            run_id,
            time.monotonic() - start
        )
        return run_id

    async def update_run_status(self, run_id: str, status: str) -> None:
        start = time.monotonic()
        try:
            self.client.table('backtest_runs') \
                .update({'status': status}) \
                .eq('id', run_id) \
                .execute()
        except Exception:
            _logger.exception(
                "Supabase update_run_status failed id=%s status=%s",
                run_id,
                status
            )
            raise
        _logger.debug(
            "Supabase update_run_status ok id=%s status=%s elapsed=%.3fs",
            run_id,
            status,
            time.monotonic() - start
        )

    async def save_metrics(self, run_id: str, metrics: Dict[str, Any]) -> None:
        payload = {
            'run_id': run_id,
            'total_trades': metrics.get('total_trades', 0),
            'win_rate': metrics.get('win_rate', 0.0),
            'total_pnl': metrics.get('total_pnl', 0.0),
            'total_return': metrics.get('total_return', 0.0),
            'max_drawdown': metrics.get('max_drawdown', 0.0),
            'sharpe': metrics.get('sharpe', 0.0),
            'sortino': metrics.get('sortino', 0.0),
            'profit_factor': metrics.get('profit_factor', 0.0),
            'expectancy': metrics.get('expectancy', 0.0),
            'avg_win': metrics.get('avg_win', 0.0),
            'avg_loss': metrics.get('avg_loss', 0.0),
            'metrics': json.dumps(metrics)
        }

        start = time.monotonic()
        try:
            self.client.table('backtest_metrics').upsert(payload).execute()
        except Exception:
            _logger.exception("Supabase save_metrics failed run_id=%s", run_id)
            raise
        _logger.debug(
            "Supabase save_metrics ok run_id=%s elapsed=%.3fs",
            run_id,
            time.monotonic() - start
        )

    async def load_kline_dataset(self, kline_dataset_id: str) -> pd.DataFrame:
        start = time.monotonic()
        try:
            response = self.client.table('kline_datasets') \
                .select('data') \
                .eq('id', kline_dataset_id) \
                .limit(1) \
                .execute()
        except Exception:
            _logger.exception(
                "Supabase load_kline_dataset failed id=%s",
                kline_dataset_id
            )
            raise

        if not response.data:
            raise ValueError(f"K线数据集不存在: {kline_dataset_id}")

        compressed_data = _decode_bytea(response.data[0].get('data'))
        if not compressed_data:
            raise ValueError(f"K线数据集为空: {kline_dataset_id}")

        json_data = zlib.decompress(compressed_data).decode()
        klines = json.loads(json_data)

        df = pd.DataFrame(klines)
        if df.empty:
            return df
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        _logger.debug(
            "Supabase load_kline_dataset ok id=%s rows=%s elapsed=%.3fs",
            kline_dataset_id,
            len(df),
            time.monotonic() - start
        )
        return df

    async def get_strategy_version(self, strategy_version_id: str) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            response = self.client.table('strategy_versions') \
                .select('id, name, version, params_schema, code_hash, created_at') \
                .eq('id', strategy_version_id) \
                .limit(1) \
                .execute()
        except Exception:
            _logger.exception(
                "Supabase get_strategy_version failed id=%s",
                strategy_version_id
            )
            raise

        if not response.data:
            raise ValueError(f"策略版本不存在: {strategy_version_id}")

        row = response.data[0]
        params_schema = row.get('params_schema')
        if isinstance(params_schema, str):
            try:
                params_schema = json.loads(params_schema)
            except json.JSONDecodeError:
                pass

        return {
            'id': row.get('id'),
            'name': row.get('name'),
            'version': row.get('version'),
            'params_schema': params_schema,
            'code_hash': row.get('code_hash'),
            'created_at': row.get('created_at')
        }


class SupabaseBacktestRepository:
    """Repository for backtest data persistence (Supabase 实现)"""

    def __init__(self):
        self.client = get_supabase_client()

    def _fetch_all(self, query, page_size: int = 1000) -> List[Dict]:
        results: List[Dict] = []
        offset = 0
        while True:
            response = query.range(offset, offset + page_size - 1).execute()
            batch = response.data or []
            results.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return results

    def save_klines(self, session_id: str, klines: List[Dict]):
        """
        Save kline data for a session (批量优化)

        Args:
            session_id: 会话ID
            klines: K线列表 [{'ts': ..., 'open': ..., 'high': ..., ...}]
        """
        _logger.debug("Supabase save_klines start session_id=%s rows=%s", session_id, len(klines))
        start = time.monotonic()
        with BatchWriter(
            'backtest_klines',
            batch_size=1000,
            upsert_on_conflict='session_id,ts'
        ) as writer:
            for k in klines:
                writer.add({
                    'id': _stable_kline_id(session_id, k['ts']),
                    'session_id': session_id,
                    'ts': k['ts'],
                    'open': k['open'],
                    'high': k['high'],
                    'low': k['low'],
                    'close': k['close'],
                    'volume': k['volume']
                })
        _logger.info(
            "Supabase save_klines ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(klines),
            time.monotonic() - start
        )

    def create_session(self, params: Dict) -> str:
        """
        Create new backtest session

        Args:
            params: Session parameters dict

        Returns:
            session_id
        """
        session_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        session_data = {
            'id': session_id,
            'created_at': now,
            'updated_at': now,
            'status': 'created',
            'symbol': params['symbol'],
            'timeframe': params['timeframe'],
            'start_ts': params['start_ts'],
            'end_ts': params['end_ts'],
            'initial_capital': params['initial_capital'],
            'fee_rate': params.get('fee_rate', 0.001),
            'slippage_bps': params.get('slippage_bps', 5),
            'leverage': params.get('leverage', 1.0),
            'strategy_name': params['strategy_name'],
            'strategy_params': json.dumps(params.get('strategy_params', {}))
        }

        start = time.monotonic()
        try:
            self.client.table('backtest_sessions').insert(session_data).execute()
        except Exception:
            _logger.exception("Supabase create_session failed id=%s", session_id)
            raise
        _logger.info(
            "Supabase create_session ok id=%s elapsed=%.3fs",
            session_id,
            time.monotonic() - start
        )

        return session_id

    def update_session_status(self, session_id: str, status: str, error: str = ""):
        """
        Update session status

        Args:
            session_id: 会话ID
            status: 状态 (created|running|completed|failed)
            error: 错误信息
        """
        now = int(datetime.utcnow().timestamp())

        start = time.monotonic()
        try:
            self.client.table('backtest_sessions').update({
                'status': status,
                'updated_at': now,
                'error_message': error
            }).eq('id', session_id).execute()
        except Exception:
            _logger.exception(
                "Supabase update_session_status failed session_id=%s status=%s",
                session_id,
                status
            )
            raise
        _logger.info(
            "Supabase update_session_status ok session_id=%s status=%s elapsed=%.3fs",
            session_id,
            status,
            time.monotonic() - start
        )

    def append_trade(self, session_id: str, trade: Dict) -> int:
        """
        Append trade record

        Args:
            session_id: 会话ID
            trade: 交易数据

        Returns:
            trade_id (注意: Supabase 自动生成,返回值可能为None)
        """
        trade_id = _stable_trade_id(session_id, trade)
        trade_data = {
            'id': trade_id,
            'session_id': session_id,
            'ts': trade['ts'],
            'symbol': trade['symbol'],
            'side': trade['side'],
            'action': trade['action'],
            'qty': trade['qty'],
            'price': trade['price'],
            'fee': trade.get('fee', 0),
            'pnl': trade.get('pnl', 0),
            'pnl_pct': trade.get('pnl_pct', 0),
            'strategy_name': trade.get('strategy_name'),
            'reason': trade.get('reason'),
            'open_trade_id': trade.get('open_trade_id')
        }

        start = time.monotonic()
        try:
            response = self.client.table('backtest_trades').upsert(
                trade_data,
                on_conflict='id',
                ignore_duplicates=True
            ).execute()
        except Exception:
            _logger.exception(
                "Supabase append_trade failed session_id=%s action=%s",
                session_id,
                trade.get('action')
            )
            raise
        _logger.debug(
            "Supabase append_trade ok session_id=%s action=%s elapsed=%.3fs",
            session_id,
            trade.get('action'),
            time.monotonic() - start
        )

        if response.data and len(response.data) > 0:
            return response.data[0].get('id', trade_id) or trade_id
        return trade_id

    def upsert_metrics(self, session_id: str, metrics: Dict):
        """
        Insert or update metrics

        Args:
            session_id: 会话ID
            metrics: 指标数据
        """
        metrics_data = {
            'session_id': session_id,
            'total_trades': metrics['total_trades'],
            'win_rate': metrics['win_rate'],
            'total_pnl': metrics['total_pnl'],
            'total_return': metrics['total_return'],
            'max_drawdown': metrics['max_drawdown'],
            'sharpe': metrics['sharpe'],
            'profit_factor': metrics['profit_factor'],
            'expectancy': metrics['expectancy'],
            'avg_win': metrics['avg_win'],
            'avg_loss': metrics['avg_loss'],
            'start_ts': metrics['start_ts'],
            'end_ts': metrics['end_ts']
        }

        start = time.monotonic()
        try:
            self.client.table('backtest_metrics').upsert(metrics_data).execute()
        except Exception:
            _logger.exception("Supabase upsert_metrics failed session_id=%s", session_id)
            raise
        _logger.debug(
            "Supabase upsert_metrics ok session_id=%s elapsed=%.3fs",
            session_id,
            time.monotonic() - start
        )

    def get_session(self, session_id: str) -> Dict:
        """
        Get session by ID

        Args:
            session_id: 会话ID

        Returns:
            Session dict or None
        """
        start = time.monotonic()
        try:
            response = self.client.table('backtest_sessions') \
                .select('*') \
                .eq('id', session_id) \
                .execute()
        except Exception:
            _logger.exception("Supabase get_session failed session_id=%s", session_id)
            raise
        _logger.debug(
            "Supabase get_session ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(response.data) if response.data else 0,
            time.monotonic() - start
        )

        if response.data:
            return response.data[0]
        return {}

    def get_metrics(self, session_id: str) -> Dict:
        """
        Get metrics by session_id

        Args:
            session_id: 会话ID

        Returns:
            Metrics dict or None
        """
        start = time.monotonic()
        try:
            response = self.client.table('backtest_metrics') \
                .select('*') \
                .eq('session_id', session_id) \
                .execute()
        except Exception:
            _logger.exception("Supabase get_metrics failed session_id=%s", session_id)
            raise
        _logger.debug(
            "Supabase get_metrics ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(response.data) if response.data else 0,
            time.monotonic() - start
        )

        if response.data:
            return response.data[0]
        return {}

    def get_trades(
        self,
        session_id: str,
        limit: Optional[int] = None,
        desc: bool = False
    ) -> List[Dict]:
        """
        Get trades for a session

        Args:
            session_id: 会话ID
            limit: 返回数量(None表示全部)
            desc: 是否倒序

        Returns:
            List of trades
        """
        query = self.client.table('backtest_trades') \
            .select('*') \
            .eq('session_id', session_id) \
            .order('ts', desc=desc)

        if limit is None:
            start = time.monotonic()
            try:
                data = self._fetch_all(query)
            except Exception:
                _logger.exception("Supabase get_trades failed session_id=%s", session_id)
                raise
            _logger.debug(
                "Supabase get_trades ok session_id=%s rows=%s elapsed=%.3fs",
                session_id,
                len(data),
                time.monotonic() - start
            )
            return data

        start = time.monotonic()
        try:
            response = query.limit(limit).execute()
        except Exception:
            _logger.exception("Supabase get_trades failed session_id=%s", session_id)
            raise
        _logger.debug(
            "Supabase get_trades ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(response.data) if response.data else 0,
            time.monotonic() - start
        )
        return response.data

    def get_klines(
        self,
        session_id: str,
        limit: Optional[int] = None,
        before: Optional[int] = None
    ) -> List[Dict]:
        """
        Get klines for a session

        Args:
            session_id: 会话ID
            limit: 返回数量(None表示全部)
            before: 时间戳上限

        Returns:
            List of klines
        """
        query = self.client.table('backtest_klines') \
            .select('*') \
            .eq('session_id', session_id)

        if before is not None:
            query = query.lt('ts', before)

        use_desc = limit is not None
        query = query.order('ts', desc=use_desc)

        if limit is None:
            start = time.monotonic()
            try:
                data = self._fetch_all(query)
            except Exception:
                _logger.exception("Supabase get_klines failed session_id=%s", session_id)
                raise
            _logger.debug(
                "Supabase get_klines ok session_id=%s rows=%s elapsed=%.3fs",
                session_id,
                len(data),
                time.monotonic() - start
            )
            return data

        start = time.monotonic()
        try:
            response = query.limit(limit).execute()
        except Exception:
            _logger.exception("Supabase get_klines failed session_id=%s", session_id)
            raise
        _logger.debug(
            "Supabase get_klines ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(response.data) if response.data else 0,
            time.monotonic() - start
        )
        data = response.data or []
        if use_desc:
            data = list(reversed(data))
        return data

    def get_latest_session(self, statuses: Optional[Iterable[str]] = None) -> Dict:
        query = self.client.table('backtest_sessions') \
            .select('*') \
            .order('updated_at', desc=True) \
            .limit(1)

        if statuses:
            query = query.in_('status', list(statuses))

        start = time.monotonic()
        try:
            response = query.execute()
        except Exception:
            _logger.exception("Supabase get_latest_session failed")
            raise
        _logger.debug(
            "Supabase get_latest_session ok rows=%s elapsed=%.3fs",
            len(response.data) if response.data else 0,
            time.monotonic() - start
        )
        if response.data:
            return response.data[0]
        return {}

    def get_events(self, session_id: str) -> List[Dict]:
        """
        Get events for a session

        Args:
            session_id: 会话ID

        Returns:
            List of events
        """
        start = time.monotonic()
        try:
            response = self.client.table('backtest_events') \
                .select('*') \
                .eq('session_id', session_id) \
                .order('ts', desc=False) \
                .execute()
        except Exception:
            _logger.exception("Supabase get_events failed session_id=%s", session_id)
            raise
        _logger.debug(
            "Supabase get_events ok session_id=%s rows=%s elapsed=%.3fs",
            session_id,
            len(response.data) if response.data else 0,
            time.monotonic() - start
        )
        return response.data
