"""
Ticker 服务 - 获取和缓存实时行情数据
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from utils.logger_utils import get_logger
from apps.api.models.ticker import Ticker
from exchange.async_manager import AsyncExchangeManager

logger = get_logger("ticker_service")


class TickerService:
    """实时行情服务

    提供缓存的实时行情数据，避免频繁调用交易所API
    """

    def __init__(self):
        self._cache: Optional[Ticker] = None
        self._cache_lock = asyncio.Lock()
        self._last_refresh: Optional[datetime] = None
        self._refresh_interval = 1.5  # 刷新间隔（秒）
        self._stale_threshold = 3.0  # 数据过期阈值（秒）
        self._exchange_manager: Optional[AsyncExchangeManager] = None
        self._symbol: Optional[str] = None

    async def initialize(self):
        """初始化服务"""
        try:
            # 导入配置
            import config.settings as config

            # 创建异步交易所管理器
            self._exchange_manager = AsyncExchangeManager()
            await self._exchange_manager.initialize()

            # 获取交易对符号
            self._symbol = config.SYMBOL

            logger.info(f"Ticker服务初始化成功 (交易对: {self._symbol})")

            # 立即刷新一次数据
            await self._refresh_ticker()

        except Exception as e:
            logger.error(f"Ticker服务初始化失败: {e}")
            raise

    def _convert_symbol_format(self, symbol: str) -> str:
        """转换交易对格式

        将配置中的格式 (BTCUSDT) 转换为交易所格式 (BTC/USDT:USDT)
        """
        # 移除 USDT 后缀
        if symbol.endswith("USDT"):
            base = symbol[:-4]
            return f"{base}/USDT:USDT"
        return symbol

    async def get_ticker(self) -> Optional[Ticker]:
        """获取缓存的行情数据

        Returns:
            Ticker对象，如果数据过期会标记stale=True
        """
        async with self._cache_lock:
            if self._cache is None:
                return None

            # 检查数据是否过期
            if self._last_refresh:
                age = (datetime.now() - self._last_refresh).total_seconds()
                if age > self._stale_threshold:
                    # 标记为过期但仍返回
                    self._cache.stale = True
                    logger.warning(f"Ticker数据已过期 ({age:.1f}秒)")

            return self._cache

    async def _refresh_ticker(self) -> Optional[Ticker]:
        """从交易所刷新行情数据

        Returns:
            刷新后的Ticker对象
        """
        if not self._exchange_manager or not self._symbol:
            logger.error("Ticker服务未初始化")
            return None

        try:
            # 转换交易对格式
            exchange_symbol = self._convert_symbol_format(self._symbol)

            # 获取行情数据
            ticker_data = await self._exchange_manager.fetch_ticker_async(exchange_symbol)

            if not ticker_data:
                logger.warning("获取行情数据失败")
                # 标记缓存为过期
                if self._cache:
                    async with self._cache_lock:
                        self._cache.stale = True
                return None

            # 创建Ticker对象
            ticker = Ticker(
                symbol=self._symbol,
                last=ticker_data.get("last"),
                bid=ticker_data.get("bid"),
                ask=ticker_data.get("ask"),
                volume=ticker_data.get("baseVolume"),
                change_24h=ticker_data.get("percentage"),
                high_24h=ticker_data.get("high"),
                low_24h=ticker_data.get("low"),
                timestamp=datetime.now(),
                stale=False
            )

            # 更新缓存
            async with self._cache_lock:
                self._cache = ticker
                self._last_refresh = datetime.now()

            logger.debug(f"Ticker数据已刷新: {ticker.symbol} @ {ticker.last}")
            return ticker

        except Exception as e:
            logger.error(f"刷新Ticker数据失败: {e}")
            # 标记缓存为过期
            if self._cache:
                async with self._cache_lock:
                    self._cache.stale = True
            return None

    async def start_background_refresh(self):
        """启动后台刷新任务"""
        logger.info(f"启动Ticker后台刷新任务 (间隔: {self._refresh_interval}秒)")

        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self._refresh_ticker()
            except asyncio.CancelledError:
                logger.info("Ticker后台刷新任务已取消")
                break
            except Exception as e:
                logger.error(f"Ticker后台刷新任务异常: {e}")
                await asyncio.sleep(5)  # 出错后等待5秒再重试


# 全局单例
ticker_service = TickerService()
