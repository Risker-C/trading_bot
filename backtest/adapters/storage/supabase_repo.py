"""
Supabase Backtest Repository - Cloud persistence layer
"""
import json
import uuid
import zlib
from datetime import datetime
from typing import Dict, List, Any, Iterable, Optional

import pandas as pd

from backtest.domain.interfaces import IDataRepository
from backtest.adapters.storage.supabase_client import get_supabase_client
from backtest.adapters.storage.batch_writer import BatchWriter


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
        response = self.client.table('kline_datasets') \
            .select('data') \
            .eq('symbol', symbol) \
            .eq('timeframe', timeframe) \
            .lte('start_ts', start_ts) \
            .gte('end_ts', end_ts) \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()

        if not response.data:
            return pd.DataFrame()

        compressed_data = _decode_bytea(response.data[0].get('data'))
        if not compressed_data:
            return pd.DataFrame()

        json_data = zlib.decompress(compressed_data).decode()
        klines = json.loads(json_data)

        df = pd.DataFrame(klines)
        if df.empty:
            return df
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

        self.client.table('kline_datasets') \
            .upsert(payload, on_conflict='symbol,timeframe,start_ts,end_ts') \
            .execute()

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

        self.client.table('backtest_runs').insert(payload).execute()
        return run_id

    async def update_run_status(self, run_id: str, status: str) -> None:
        self.client.table('backtest_runs') \
            .update({'status': status}) \
            .eq('id', run_id) \
            .execute()

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

        self.client.table('backtest_metrics').upsert(payload).execute()

    async def load_kline_dataset(self, kline_dataset_id: str) -> pd.DataFrame:
        response = self.client.table('kline_datasets') \
            .select('data') \
            .eq('id', kline_dataset_id) \
            .limit(1) \
            .execute()

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
        return df

    async def get_strategy_version(self, strategy_version_id: str) -> Dict[str, Any]:
        response = self.client.table('strategy_versions') \
            .select('id, name, version, params_schema, code_hash, created_at') \
            .eq('id', strategy_version_id) \
            .limit(1) \
            .execute()

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
        with BatchWriter('backtest_klines', batch_size=1000) as writer:
            for k in klines:
                writer.add({
                    'session_id': session_id,
                    'ts': k['ts'],
                    'open': k['open'],
                    'high': k['high'],
                    'low': k['low'],
                    'close': k['close'],
                    'volume': k['volume']
                })

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

        self.client.table('backtest_sessions').insert(session_data).execute()

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

        self.client.table('backtest_sessions').update({
            'status': status,
            'updated_at': now,
            'error_message': error
        }).eq('id', session_id).execute()

    def append_trade(self, session_id: str, trade: Dict) -> int:
        """
        Append trade record

        Args:
            session_id: 会话ID
            trade: 交易数据

        Returns:
            trade_id (注意: Supabase 自动生成,返回值可能为None)
        """
        trade_data = {
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

        response = self.client.table('backtest_trades').insert(trade_data).execute()

        # 返回自动生成的 ID (如果有)
        if response.data and len(response.data) > 0:
            return response.data[0].get('id', 0)
        return 0

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

        self.client.table('backtest_metrics').upsert(metrics_data).execute()

    def get_session(self, session_id: str) -> Dict:
        """
        Get session by ID

        Args:
            session_id: 会话ID

        Returns:
            Session dict or None
        """
        response = self.client.table('backtest_sessions') \
            .select('*') \
            .eq('id', session_id) \
            .execute()

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
        response = self.client.table('backtest_metrics') \
            .select('*') \
            .eq('session_id', session_id) \
            .execute()

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
            return self._fetch_all(query)

        response = query.limit(limit).execute()
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
            .eq('session_id', session_id) \
            .order('ts', desc=False)

        if before is not None:
            query = query.lt('ts', before)

        if limit is None:
            return self._fetch_all(query)

        response = query.limit(limit).execute()
        return response.data

    def get_latest_session(self, statuses: Optional[Iterable[str]] = None) -> Dict:
        query = self.client.table('backtest_sessions') \
            .select('*') \
            .order('updated_at', desc=True) \
            .limit(1)

        if statuses:
            query = query.in_('status', list(statuses))

        response = query.execute()
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
        response = self.client.table('backtest_events') \
            .select('*') \
            .eq('session_id', session_id) \
            .order('ts', desc=False) \
            .execute()

        return response.data
