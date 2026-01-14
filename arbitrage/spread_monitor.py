"""
价差监控器 - 并行监控多个交易所价格并计算价差
"""
import time
import threading
from typing import Dict, List, Optional
from collections import deque
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.logger_utils import get_logger
from exchange.manager import ExchangeManager
from exchange.interface import TickerData
from .models import SpreadData

logger = get_logger("spread_monitor")


class SpreadMonitor:
    """价差监控器"""

    def __init__(self, exchange_manager: ExchangeManager, config: Dict):
        """
        初始化价差监控器

        Args:
            exchange_manager: 交易所管理器
            config: 配置字典
        """
        self.exchange_manager = exchange_manager
        self.config = config

        # 配置参数
        self.symbol = config.get("symbol", "BTCUSDT")
        self.exchanges = config.get("exchanges", ["bitget", "binance", "okx"])
        self.monitor_interval = config.get("monitor_interval", 1)  # 秒
        self.history_size = config.get("history_size", 100)

        # 价差历史记录
        self.spread_history: deque = deque(maxlen=self.history_size)

        # 最新价格缓存
        self.latest_prices: Dict[str, TickerData] = {}

        # 监控控制
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None

        logger.info(f"价差监控器初始化: symbol={self.symbol}, exchanges={self.exchanges}")

    def fetch_prices(self) -> Dict[str, TickerData]:
        """
        并行获取所有交易所的价格

        Returns:
            交易所名称 -> TickerData 的字典
        """
        prices = {}

        # 使用线程池并行获取价格
        with ThreadPoolExecutor(max_workers=len(self.exchanges)) as executor:
            # 提交所有任务
            future_to_exchange = {}
            for exchange_name in self.exchanges:
                try:
                    exchange = self.exchange_manager.get_exchange(exchange_name)
                    future = executor.submit(exchange.get_ticker, self.symbol)
                    future_to_exchange[future] = exchange_name
                except Exception as e:
                    logger.error(f"获取交易所 {exchange_name} 失败: {e}")

            # 收集结果
            for future in as_completed(future_to_exchange):
                exchange_name = future_to_exchange[future]
                try:
                    ticker = future.result(timeout=5)
                    if ticker:
                        prices[exchange_name] = ticker
                        logger.debug(f"{exchange_name}: {ticker.last:.2f}")
                except Exception as e:
                    logger.error(f"获取 {exchange_name} 价格失败: {e}")

        self.latest_prices = prices
        return prices

    def calculate_spreads(self, prices: Dict[str, TickerData]) -> List[SpreadData]:
        """
        计算所有交易所对之间的价差

        Args:
            prices: 交易所价格字典

        Returns:
            价差数据列表
        """
        spreads = []
        exchanges = list(prices.keys())

        # 计算所有交易所对的价差
        for i, exchange_a in enumerate(exchanges):
            for exchange_b in exchanges[i + 1:]:
                ticker_a = prices[exchange_a]
                ticker_b = prices[exchange_b]

                # 计算两个方向的价差
                # 方向1: 在A买入，在B卖出
                spread_ab = self._calculate_spread(ticker_a, ticker_b, exchange_a, exchange_b)
                if spread_ab:
                    spreads.append(spread_ab)

                # 方向2: 在B买入，在A卖出
                spread_ba = self._calculate_spread(ticker_b, ticker_a, exchange_b, exchange_a)
                if spread_ba:
                    spreads.append(spread_ba)

        return spreads

    def _calculate_spread(self, ticker_buy: TickerData, ticker_sell: TickerData,
                          exchange_buy: str, exchange_sell: str) -> Optional[SpreadData]:
        """
        计算单个方向的价差

        Args:
            ticker_buy: 买入交易所的ticker
            ticker_sell: 卖出交易所的ticker
            exchange_buy: 买入交易所名称
            exchange_sell: 卖出交易所名称

        Returns:
            价差数据
        """
        try:
            # 买入价格 = ask (卖一价)
            buy_price = ticker_buy.ask
            # 卖出价格 = bid (买一价)
            sell_price = ticker_sell.bid

            if not buy_price or not sell_price or buy_price <= 0 or sell_price <= 0:
                return None

            # 计算价差百分比
            spread_pct = (sell_price - buy_price) / buy_price * 100

            return SpreadData(
                exchange_a=exchange_buy,
                exchange_b=exchange_sell,
                symbol=self.symbol,
                buy_price=buy_price,
                sell_price=sell_price,
                spread_pct=spread_pct,
                timestamp=int(time.time() * 1000)
            )

        except Exception as e:
            logger.error(f"计算价差失败 ({exchange_buy}->{exchange_sell}): {e}")
            return None

    def update(self) -> List[SpreadData]:
        """
        更新价格和价差

        Returns:
            最新的价差列表
        """
        # 获取价格
        prices = self.fetch_prices()

        if len(prices) < 2:
            logger.warning(f"获取到的价格不足2个: {len(prices)}")
            return []

        # 计算价差
        spreads = self.calculate_spreads(prices)

        # 保存到历史记录
        for spread in spreads:
            self.spread_history.append(spread)

        logger.debug(f"更新价差: 获取{len(prices)}个价格, 计算{len(spreads)}个价差")

        return spreads

    def get_latest_spreads(self) -> List[SpreadData]:
        """
        获取最新的价差

        Returns:
            最新一轮的价差列表
        """
        if not self.spread_history:
            return []

        # 获取最新时间戳
        latest_timestamp = self.spread_history[-1].timestamp

        # 返回最新时间戳的所有价差
        return [s for s in self.spread_history if s.timestamp == latest_timestamp]

    def get_spread_history(self, limit: int = None) -> List[SpreadData]:
        """
        获取历史价差

        Args:
            limit: 限制返回数量

        Returns:
            历史价差列表
        """
        if limit:
            return list(self.spread_history)[-limit:]
        return list(self.spread_history)

    def start(self):
        """启动监控"""
        if self.running:
            logger.warning("价差监控器已在运行")
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("价差监控器已启动")

    def stop(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("价差监控器已停止")

    def _monitor_loop(self):
        """监控循环"""
        logger.info("价差监控循环开始")

        while self.running:
            try:
                # 更新价差
                spreads = self.update()

                # 记录最大价差
                if spreads:
                    max_spread = max(spreads, key=lambda s: s.spread_pct)
                    if max_spread.spread_pct > 0.1:  # 价差 > 0.1%
                        logger.info(f"最大价差: {max_spread}")

                # 等待下一次更新
                time.sleep(self.monitor_interval)

            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(self.monitor_interval)

        logger.info("价差监控循环结束")
