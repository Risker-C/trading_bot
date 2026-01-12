"""
异步交易所管理器
支持 ccxt async_support 模块，提供高性能的异步交易所操作
"""

import ccxt.async_support as ccxt_async
import asyncio
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime
import logging

# 导入配置
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

logger = logging.getLogger(__name__)


class AsyncExchangeManager:
    """
    异步交易所管理器
    
    功能:
    - 异步初始化交易所连接
    - 并发获取多个交易对数据
    - 并发获取多时间周期数据
    - 自动重试和错误处理
    - 资源管理和连接池
    """
    
    def __init__(self, exchange_name: str = None):
        """
        初始化异步交易所管理器
        
        Args:
            exchange_name: 交易所名称，默认使用配置中的 ACTIVE_EXCHANGE
        """
        self.exchange_name = exchange_name or getattr(config, 'ACTIVE_EXCHANGE', 'bitget')
        self.exchange: Optional[ccxt_async.Exchange] = None
        self.initialized = False
        self.max_retries = 3
        self.retry_delay = 1.0  # 秒
        
        logger.info(f"AsyncExchangeManager 初始化: {self.exchange_name}")
    
    async def initialize(self) -> bool:
        """
        初始化异步交易所连接
        
        Returns:
            bool: 初始化是否成功
        """
        if self.initialized:
            logger.warning("交易所已经初始化")
            return True
        
        try:
            # 根据交易所名称创建实例
            exchange_class = getattr(ccxt_async, self.exchange_name.lower())

            # 配置参数
            exchange_config = {
                'apiKey': getattr(config, 'API_KEY', ''),
                'secret': getattr(config, 'API_SECRET', ''),
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # 合约交易
                }
            }

            # Bitget 需要 passphrase
            if self.exchange_name.lower() == 'bitget':
                exchange_config['password'] = getattr(config, 'API_PASSPHRASE', '')

            # 创建交易所实例
            self.exchange = exchange_class(exchange_config)
            
            # 加载市场数据
            await self.exchange.load_markets()
            
            self.initialized = True
            logger.info(f"✓ {self.exchange_name} 异步交易所初始化成功")
            logger.info(f"  支持的市场数量: {len(self.exchange.markets)}")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ 交易所初始化失败: {e}")
            self.initialized = False
            return False
    
    async def fetch_ticker_async(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        异步获取 ticker 数据
        
        Args:
            symbol: 交易对符号，如 'BTC/USDT:USDT'
            
        Returns:
            Dict: ticker 数据，包含 last, bid, ask, volume 等
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return None
        
        for attempt in range(self.max_retries):
            try:
                ticker = await self.exchange.fetch_ticker(symbol)
                logger.debug(f"获取 {symbol} ticker: {ticker['last']}")
                return ticker
                
            except Exception as e:
                logger.warning(f"获取 ticker 失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"获取 ticker 最终失败: {symbol}")
                    return None
    
    async def fetch_ohlcv_async(
        self, 
        symbol: str, 
        timeframe: str = '15m', 
        limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        异步获取 OHLCV K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期，如 '1m', '5m', '15m', '1h', '4h', '1d'
            limit: 获取的K线数量
            
        Returns:
            DataFrame: 包含 timestamp, open, high, low, close, volume 列
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return None
        
        for attempt in range(self.max_retries):
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                
                # 转换为 DataFrame
                df = pd.DataFrame(
                    ohlcv, 
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                logger.debug(f"获取 {symbol} {timeframe} K线: {len(df)} 条")
                return df
                
            except Exception as e:
                logger.warning(f"获取 OHLCV 失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"获取 OHLCV 最终失败: {symbol} {timeframe}")
                    return None
    
    async def fetch_multiple_timeframes(
        self, 
        symbol: str, 
        timeframes: List[str],
        limit: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """
        并发获取多个时间周期的K线数据
        
        Args:
            symbol: 交易对符号
            timeframes: 时间周期列表，如 ['5m', '15m', '1h']
            limit: 每个时间周期获取的K线数量
            
        Returns:
            Dict: {timeframe: DataFrame} 的字典
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return 
        
        logger.info(f"并发获取 {symbol} 的 {len(timeframes)} 个时间周期数据")
        
        # 创建并发任务
        tasks = [
            self.fetch_ohlcv_async(symbol, tf, limit)
            for tf in timeframes
        ]
        
        # 并发执行
        start_time = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 整理结果
        data_dict = {}
        for tf, result in zip(timeframes, results):
            if isinstance(result, Exception):
                logger.error(f"获取 {tf} 数据失败: {result}")
            elif result is not None:
                data_dict[tf] = result
        
        logger.info(f"✓ 并发获取完成: {len(data_dict)}/{len(timeframes)} 成功, 耗时 {elapsed:.2f}s")
        return data_dict
    
    async def fetch_multiple_symbols(
        self, 
        symbols: List[str], 
        timeframe: str = '15m',
        limit: int = 100
    ) -> Dict[str, pd.DataFrame]:
        """
        并发获取多个交易对的K线数据
        
        Args:
            symbols: 交易对列表
            timeframe: 时间周期
            limit: K线数量
            
        Returns:
            Dict: {symbol: DataFrame} 的字典
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return {}
        
        logger.info(f"并发获取 {len(symbols)} 个交易对的 {timeframe} 数据")
        
        # 创建并发任务
        tasks = [
            self.fetch_ohlcv_async(symbol, timeframe, limit)
            for symbol in symbols
        ]
        
        # 并发执行
        start_time = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # 整理结果
        data_dict = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"获取 {symbol} 数据失败: {result}")
            elif result is not None:
                data_dict[symbol] = result
        
        logger.info(f"✓ 并发获取完成: {len(data_dict)}/{len(symbols)} 成功, 耗时 {elapsed:.2f}s")
        return data_dict
    
    async def fetch_balance_async(self) -> Optional[Dict[str, Any]]:
        """
        异步获取账户余额
        
        Returns:
            Dict: 账户余额信息
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return None
        
        try:
            balance = await self.exchange.fetch_balance()
            logger.debug(f"获取账户余额成功")
            return balance
            
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return None
    
    async def fetch_positions_async(self, symbols: List[str] = None) -> Optional[List[Dict]]:
        """
        异步获取持仓信息
        
        Args:
            symbols: 交易对列表，None 表示获取所有持仓
            
        Returns:
            List[Dict]: 持仓信息列表
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return None
        
        try:
            positions = await self.exchange.fetch_positions(symbols)
            logger.debug(f"获取持仓信息: {len(positions)} 个")
            return positions
            
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return None
    
    async def create_order_async(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float = None,
        params: Dict = None
    ) -> Optional[Dict]:
        """
        异步创建订单
        
        Args:
            symbol: 交易对
            order_type: 订单类型 'market' 或 'limit'
            side: 'buy' 或 'sell'
            amount: 数量
            price: 价格（限价单需要）
            params: 额外参数
            
        Returns:
            Dict: 订单信息
        """
        if not self.initialized:
            logger.error("交易所未初始化")
            return None
        
        try:
            order = await self.exchange.create_order(
                symbol, order_type, side, amount, price, params
            )
            logger.info(f"✓ 创建订单成功: {side} {amount} {symbol} @ {price or 'market'}")
            return order
            
        except Exception as e:
            logger.error(f"✗ 创建订单失败: {e}")
            return None
    
    async def close(self):
        """
        关闭交易所连接，释放资源
        """
        if self.exchange:
            try:
                await self.exchange.close()
                logger.info(f"✓ {self.exchange_name} 连接已关闭")
            except Exception as e:
                logger.error(f"关闭连接时出错: {e}")
            finally:
                self.exchange = None
                self.initialized = False
    
    async def __aenter__(self):
        """支持 async with 语法"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """支持 async with 语法"""
        await self.close()


# 便捷函数
async def get_market_data(
    symbol: str = None,
    timeframes: List[str] = None,
    limit: int = 100
) -> Dict[str, pd.DataFrame]:
    """
    便捷函数：获取市场数据

    Args:
        symbol: 交易对
        timeframes: 时间周期列表，默认 ['5m', '15m', '1h']
        limit: K线数量

    Returns:
        Dict: {timeframe: DataFrame}
    """
    if symbol is None:
        symbol = getattr(config, 'SYMBOL', 'BTC/USDT:USDT')
    if timeframes is None:
        timeframes = ['5m', '15m', '1h']

    async with AsyncExchangeManager() as manager:
        return await manager.fetch_multiple_timeframes(symbol, timeframes, limit)


async def get_multiple_symbols_data(
    symbols: List[str],
    timeframe: str = None,
    limit: int = 100
) -> Dict[str, pd.DataFrame]:
    """
    便捷函数：获取多个交易对数据

    Args:
        symbols: 交易对列表
        timeframe: 时间周期
        limit: K线数量

    Returns:
        Dict: {symbol: DataFrame}
    """
    if timeframe is None:
        timeframe = getattr(config, 'TIMEFRAME', '15m')

    async with AsyncExchangeManager() as manager:
        return await manager.fetch_multiple_symbols(symbols, timeframe, limit)


# 测试代码
async def test_async_manager():
    """测试异步交易所管理器"""
    print("=" * 60)
    print("测试异步交易所管理器")
    print("=" * 60)

    # 获取配置
    symbol = getattr(config, 'SYMBOL', 'BTC/USDT:USDT')

    async with AsyncExchangeManager() as manager:
        # 测试1: 获取单个 ticker
        print("\n[测试1] 获取 ticker")
        ticker = await manager.fetch_ticker_async(symbol)
        if ticker:
            print(f"✓ {symbol} 价格: {ticker['last']}")

        # 测试2: 获取单个时间周期K线
        print("\n[测试2] 获取单个时间周期K线")
        df = await manager.fetch_ohlcv_async(symbol, '15m', 10)
        if df is not None:
            print(f"✓ 获取 {len(df)} 条K线")
            print(df.tail(3))

        # 测试3: 并发获取多时间周期
        print("\n[测试3] 并发获取多时间周期")
        timeframes = ['5m', '15m', '1h', '4h']
        data_dict = await manager.fetch_multiple_timeframes(symbol, timeframes, 10)
        for tf, df in data_dict.items():
            print(f"✓ {tf}: {len(df)} 条K线")
        
        # 测试4: 并发获取多个交易对
        print("\n[测试4] 并发获取多个交易对")
        symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']
        symbol_data = await manager.fetch_multiple_symbols(symbols, '15m', 10)
        for symbol, df in symbol_data.items():
            print(f"✓ {symbol}: {len(df)} 条K线")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行测试
    asyncio.run(test_async_manager())
