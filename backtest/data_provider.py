"""
Historical Data Provider - Fetch klines from Bitget
"""
import pandas as pd
from datetime import datetime
from exchange.adapters.bitget_adapter import BitgetAdapter
from config.settings import settings as config


class HistoricalDataProvider:
    """Fetch historical kline data from exchange"""

    def __init__(self):
        self.adapter = BitgetAdapter(config.EXCHANGE_CONFIG)
        if not self.adapter.is_connected():
            self.adapter.connect()

    def fetch_klines(self, symbol: str, timeframe: str, start_ts: int, end_ts: int) -> pd.DataFrame:
        """
        Fetch historical klines

        Args:
            symbol: Trading pair (e.g., BTC/USDT:USDT)
            timeframe: Timeframe (e.g., 15m, 1h)
            start_ts: Start timestamp (Unix seconds)
            end_ts: End timestamp (Unix seconds)

        Returns:
            DataFrame with OHLCV data
        """
        start_ms = start_ts * 1000
        end_ms = end_ts * 1000

        all_klines = []
        current_start = start_ms

        while current_start < end_ms:
            klines = self.adapter.exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=current_start,
                limit=1000,
                params={"productType": "USDT-FUTURES"}
            )

            if not klines:
                break

            all_klines.extend(klines)
            current_start = klines[-1][0] + 1

            if len(klines) < 1000:
                break

        if not all_klines:
            return pd.DataFrame()

        df = pd.DataFrame(
            all_klines,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        return df[df.index <= pd.to_datetime(end_ms, unit='ms')]
