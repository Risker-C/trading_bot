"""
套利机会检测器 - 盈利能力计算、机会过滤和排序
"""
from typing import List, Dict, Optional, Tuple
from logger_utils import get_logger
from exchange.manager import ExchangeManager
from .models import SpreadData, ArbitrageOpportunity

logger = get_logger("opportunity_detector")


class OpportunityDetector:
    """套利机会检测器"""

    def __init__(self, exchange_manager: ExchangeManager, config: Dict):
        """
        初始化机会检测器

        Args:
            exchange_manager: 交易所管理器
            config: 配置字典
        """
        self.exchange_manager = exchange_manager
        self.config = config

        # 配置参数
        self.symbol = config.get("symbol", "BTCUSDT")
        self.min_spread_threshold = config.get("min_spread_threshold", 0.3)  # %
        self.min_net_profit_threshold = config.get("min_net_profit_threshold", 1.0)  # USDT
        self.min_profit_ratio = config.get("min_profit_ratio", 0.5)  # 净利润/毛利润
        self.min_orderbook_depth_usdt = config.get("min_orderbook_depth_usdt", 5000)
        self.min_orderbook_depth_multiplier = config.get("min_orderbook_depth_multiplier", 3.0)

        # 手续费配置
        self.fee_rates = config.get("fee_rates", {
            "bitget": {"maker": 0.0002, "taker": 0.0006},
            "binance": {"maker": 0.0002, "taker": 0.0004},
            "okx": {"maker": 0.0002, "taker": 0.0005},
        })

        logger.info(f"机会检测器初始化: min_spread={self.min_spread_threshold}%, "
                   f"min_profit={self.min_net_profit_threshold} USDT")

    def detect_opportunities(self, spreads: List[SpreadData],
                           test_amount: float = 100) -> List[ArbitrageOpportunity]:
        """
        从价差数据中检测套利机会

        Args:
            spreads: 价差数据列表
            test_amount: 测试金额(USDT)

        Returns:
            套利机会列表
        """
        opportunities = []

        for spread in spreads:
            # 过滤1: 最小价差
            if spread.spread_pct < self.min_spread_threshold:
                continue

            # 创建机会对象
            opportunity = self._create_opportunity(spread, test_amount)
            if not opportunity:
                continue

            # 过滤2: 最小净利润
            if opportunity.net_profit < self.min_net_profit_threshold:
                continue

            # 过滤3: 利润比例
            profit_ratio = opportunity.net_profit / opportunity.gross_profit if opportunity.gross_profit > 0 else 0
            if profit_ratio < self.min_profit_ratio:
                continue

            # 过滤4: 订单簿深度
            if not self._check_orderbook_depth(opportunity, test_amount):
                continue

            opportunities.append(opportunity)

        # 排序: 按净利润降序
        opportunities.sort(key=lambda x: x.net_profit, reverse=True)

        logger.debug(f"检测到 {len(opportunities)} 个套利机会 (从 {len(spreads)} 个价差)")

        return opportunities

    def _create_opportunity(self, spread: SpreadData, amount: float) -> Optional[ArbitrageOpportunity]:
        """
        从价差数据创建套利机会

        Args:
            spread: 价差数据
            amount: 交易金额

        Returns:
            套利机会对象
        """
        try:
            # 获取手续费率
            buy_fee_rate = self._get_fee_rate(spread.exchange_a, "taker")  # 市价单用taker费率
            sell_fee_rate = self._get_fee_rate(spread.exchange_b, "taker")

            # 估算滑点
            buy_slippage = self._estimate_slippage(spread.exchange_a, amount)
            sell_slippage = self._estimate_slippage(spread.exchange_b, amount)

            # 计算毛利润 (每USDT)
            gross_profit_per_unit = spread.sell_price - spread.buy_price

            # 计算净利润
            net_profit = self._calculate_net_profit(
                buy_price=spread.buy_price,
                sell_price=spread.sell_price,
                amount=amount,
                buy_fee_rate=buy_fee_rate,
                sell_fee_rate=sell_fee_rate,
                buy_slippage=buy_slippage,
                sell_slippage=sell_slippage
            )

            # 获取订单簿深度
            buy_depth = self._get_orderbook_depth(spread.exchange_a)
            sell_depth = self._get_orderbook_depth(spread.exchange_b)

            # 计算风险评分 (0-1, 越低越好)
            risk_score = self._calculate_risk_score(
                spread=spread,
                buy_depth=buy_depth,
                sell_depth=sell_depth,
                buy_slippage=buy_slippage,
                sell_slippage=sell_slippage
            )

            return ArbitrageOpportunity(
                buy_exchange=spread.exchange_a,
                sell_exchange=spread.exchange_b,
                symbol=spread.symbol,
                buy_price=spread.buy_price,
                sell_price=spread.sell_price,
                spread_pct=spread.spread_pct,
                gross_profit=gross_profit_per_unit,
                net_profit=net_profit,
                buy_exchange_fee=buy_fee_rate,
                sell_exchange_fee=sell_fee_rate,
                estimated_buy_slippage=buy_slippage,
                estimated_sell_slippage=sell_slippage,
                timestamp=spread.timestamp,
                buy_orderbook_depth=buy_depth,
                sell_orderbook_depth=sell_depth,
                risk_score=risk_score
            )

        except Exception as e:
            logger.error(f"创建机会失败 ({spread.exchange_a}->{spread.exchange_b}): {e}")
            return None

    def _calculate_net_profit(self, buy_price: float, sell_price: float, amount: float,
                             buy_fee_rate: float, sell_fee_rate: float,
                             buy_slippage: float, sell_slippage: float) -> float:
        """
        计算净利润

        Args:
            buy_price: 买入价格
            sell_price: 卖出价格
            amount: 交易金额(USDT)
            buy_fee_rate: 买入手续费率
            sell_fee_rate: 卖出手续费率
            buy_slippage: 买入滑点率
            sell_slippage: 卖出滑点率

        Returns:
            净利润(USDT)
        """
        # 毛利润
        gross_profit = (sell_price - buy_price) * amount / buy_price

        # 手续费
        buy_fee = amount * buy_fee_rate
        sell_fee = amount * sell_fee_rate
        total_fees = buy_fee + sell_fee

        # 滑点成本
        buy_slippage_cost = amount * buy_slippage
        sell_slippage_cost = amount * sell_slippage
        total_slippage = buy_slippage_cost + sell_slippage_cost

        # 安全缓冲 (0.1%)
        buffer = amount * 0.001

        # 净利润
        net_profit = gross_profit - total_fees - total_slippage - buffer

        return net_profit

    def _get_fee_rate(self, exchange_name: str, order_type: str = "taker") -> float:
        """
        获取交易所手续费率

        Args:
            exchange_name: 交易所名称
            order_type: 订单类型 (maker/taker)

        Returns:
            手续费率
        """
        exchange_fees = self.fee_rates.get(exchange_name.lower(), {})
        return exchange_fees.get(order_type, 0.0006)  # 默认0.06%

    def _estimate_slippage(self, exchange_name: str, amount: float) -> float:
        """
        估算滑点

        Args:
            exchange_name: 交易所名称
            amount: 交易金额

        Returns:
            滑点率
        """
        # 简化估算: 基于交易金额
        # 实际应该基于订单簿深度动态计算
        if amount < 100:
            return 0.0001  # 0.01%
        elif amount < 500:
            return 0.0002  # 0.02%
        elif amount < 1000:
            return 0.0003  # 0.03%
        else:
            return 0.0005  # 0.05%

    def _get_orderbook_depth(self, exchange_name: str) -> Optional[float]:
        """
        获取订单簿深度

        Args:
            exchange_name: 交易所名称

        Returns:
            订单簿深度(USDT)
        """
        try:
            exchange = self.exchange_manager.get_exchange(exchange_name)
            orderbook = exchange.get_orderbook(self.symbol, limit=20)

            if not orderbook:
                return None

            # 计算买卖盘深度
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

            bid_depth = sum(price * amount for price, amount in bids) if bids else 0
            ask_depth = sum(price * amount for price, amount in asks) if asks else 0

            # 返回较小的深度
            return min(bid_depth, ask_depth) if bid_depth > 0 and ask_depth > 0 else None

        except Exception as e:
            logger.debug(f"获取订单簿深度失败 ({exchange_name}): {e}")
            return None

    def _check_orderbook_depth(self, opportunity: ArbitrageOpportunity, amount: float) -> bool:
        """
        检查订单簿深度是否充足

        Args:
            opportunity: 套利机会
            amount: 交易金额

        Returns:
            是否通过检查
        """
        # 检查买入交易所深度
        if opportunity.buy_orderbook_depth:
            if opportunity.buy_orderbook_depth < self.min_orderbook_depth_usdt:
                return False
            if opportunity.buy_orderbook_depth < amount * self.min_orderbook_depth_multiplier:
                return False

        # 检查卖出交易所深度
        if opportunity.sell_orderbook_depth:
            if opportunity.sell_orderbook_depth < self.min_orderbook_depth_usdt:
                return False
            if opportunity.sell_orderbook_depth < amount * self.min_orderbook_depth_multiplier:
                return False

        return True

    def _calculate_risk_score(self, spread: SpreadData, buy_depth: Optional[float],
                             sell_depth: Optional[float], buy_slippage: float,
                             sell_slippage: float) -> float:
        """
        计算风险评分

        Args:
            spread: 价差数据
            buy_depth: 买入订单簿深度
            sell_depth: 卖出订单簿深度
            buy_slippage: 买入滑点
            sell_slippage: 卖出滑点

        Returns:
            风险评分 (0-1, 越低越好)
        """
        risk_score = 0.0

        # 价差风险: 价差越小风险越高
        if spread.spread_pct < 0.5:
            risk_score += 0.3
        elif spread.spread_pct < 1.0:
            risk_score += 0.2
        else:
            risk_score += 0.1

        # 深度风险: 深度不足风险高
        if buy_depth and buy_depth < 10000:
            risk_score += 0.2
        if sell_depth and sell_depth < 10000:
            risk_score += 0.2

        # 滑点风险: 滑点大风险高
        total_slippage = buy_slippage + sell_slippage
        if total_slippage > 0.001:
            risk_score += 0.2
        elif total_slippage > 0.0005:
            risk_score += 0.1

        return min(risk_score, 1.0)
