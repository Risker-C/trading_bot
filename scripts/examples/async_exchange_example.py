"""
异步交易所接口示例 - 使用 ccxt.async_support

这个文件展示如何将同步的 ccxt 调用改造为异步版本，
可以显著提升 API 调用性能，特别是在需要并发获取多个交易对数据时。

性能对比：
- 同步：获取3个交易对数据需要 3 * 200ms = 600ms
- 异步：获取3个交易对数据需要 max(200ms) = 200ms（并发）
"""
import asyncio
import ccxt.async_support as ccxt_async
from typing import Dict, List
from config.settings import settings as config


class AsyncExchangeManager:
    """异步交易所管理器"""

    def __init__(self):
        self.exchange = None
        self.initialized = False

    async def initialize(self):
        """初始化异步交易所连接"""
        exchange_config = config.EXCHANGE_CONFIG

        self.exchange = ccxt_async.bitget({
            'apiKey': exchange_config['api_key'],
            'secret': exchange_config['api_secret'],
            'password': exchange_config['api_password'],
            'enableRateLimit': True,
        })

        self.initialized = True
        print("✅ 异步交易所连接已初始化")

    async def fetch_ticker_async(self, symbol: str) -> Dict:
        """异步获取ticker数据"""
        if not self.initialized:
            await self.initialize()

        ticker = await self.exchange.fetch_ticker(symbol)
        return ticker

    async def fetch_multiple_tickers(self, symbols: List[str]) -> Dict[str, Dict]:
        """并发获取多个交易对的ticker数据"""
        if not self.initialized:
            await self.initialize()

        # 创建并发任务
        tasks = [self.fetch_ticker_async(symbol) for symbol in symbols]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 组装结果
        tickers = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                print(f"❌ 获取 {symbol} 失败: {result}")
            else:
                tickers[symbol] = result

        return tickers

    async def close(self):
        """关闭连接"""
        if self.exchange:
            await self.exchange.close()
            print("✅ 异步交易所连接已关闭")


async def example_usage():
    """使用示例"""
    manager = AsyncExchangeManager()

    try:
        # 示例1：获取单个ticker
        print("\n=== 示例1：获取单个ticker ===")
        ticker = await manager.fetch_ticker_async("BTC/USDT:USDT")
        print(f"BTC价格: {ticker['last']}")

        # 示例2：并发获取多个ticker
        print("\n=== 示例2：并发获取多个ticker ===")
        symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
        tickers = await manager.fetch_multiple_tickers(symbols)

        for symbol, ticker in tickers.items():
            print(f"{symbol}: {ticker['last']}")

    finally:
        await manager.close()


if __name__ == "__main__":
    # 运行异步示例
    asyncio.run(example_usage())
