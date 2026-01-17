"""
数据服务 - 负责K线数据获取、压缩、去重
"""
import zlib
import json
import hashlib
from typing import List, Dict, Any
import pandas as pd

from backtest.domain.interfaces import IDataRepository, IFeatureCache
from backtest.data_provider import HistoricalDataProvider


class DataService:
    """数据服务"""

    def __init__(
        self,
        repo: IDataRepository,
        cache: IFeatureCache,
        provider: HistoricalDataProvider
    ):
        self.repo = repo
        self.cache = cache
        self.provider = provider

    def compress_klines(self, klines: pd.DataFrame) -> bytes:
        """压缩K线数据（约50%压缩率）"""
        # 转换为字典列表
        klines_dict = klines.reset_index().to_dict('records')

        # 转换timestamp为毫秒
        for item in klines_dict:
            if 'timestamp' in item:
                item['timestamp'] = int(item['timestamp'].timestamp() * 1000)

        # JSON序列化并压缩
        json_data = json.dumps(klines_dict, separators=(',', ':'))
        return zlib.compress(json_data.encode(), level=6)

    def decompress_klines(self, data: bytes) -> pd.DataFrame:
        """解压K线数据"""
        json_data = zlib.decompress(data).decode()
        klines = json.loads(json_data)

        df = pd.DataFrame(klines)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

        return df

    async def get_or_fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> tuple[str, pd.DataFrame]:
        """获取或拉取K线数据（带缓存和去重）"""

        # 1. 尝试从数据库获取
        df = await self.repo.get_candles(symbol, timeframe, start_ts, end_ts)

        if not df.empty:
            # 找到现有数据集ID
            cache_key = f"kline:{symbol}:{timeframe}:{start_ts}:{end_ts}"
            dataset_id = await self.cache.get(cache_key)
            if dataset_id:
                return dataset_id, df

        # 2. 从交易所拉取
        df = self.provider.fetch_klines(symbol, timeframe, start_ts, end_ts)

        if df.empty:
            raise ValueError(f"无法获取K线数据: {symbol} {timeframe}")

        # 3. 压缩并保存
        compressed_data = self.compress_klines(df)
        dataset_id = await self.repo.save_kline_dataset(
            symbol, timeframe, start_ts, end_ts, compressed_data
        )

        # 4. 缓存dataset_id
        cache_key = f"kline:{symbol}:{timeframe}:{start_ts}:{end_ts}"
        await self.cache.set(cache_key, dataset_id, ttl=3600)

        return dataset_id, df
