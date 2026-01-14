"""
流动性验证器 (Liquidity Validator)
检查订单簿深度，防止流动性不足导致滑点过大
"""
from decimal import Decimal
from typing import Tuple, Optional, Dict, Any
from config.settings import settings as config
from utils.logger_utils import get_logger

logger = get_logger("liquidity_validator")


class LiquidityValidator:
    """流动性验证器"""

    def __init__(self):
        self.enabled = getattr(config, 'LIQUIDITY_VALIDATION_ENABLED', True)
        self.depth_multiplier = getattr(config, 'MIN_ORDERBOOK_DEPTH_MULTIPLIER', 2.0)
        self.min_depth_usdt = getattr(config, 'MIN_ORDERBOOK_DEPTH_USDT', 1000)
        self.data_freshness = getattr(config, 'ORDERBOOK_DATA_FRESHNESS_SECONDS', 5.0)
        self.insufficient_action = getattr(config, 'LIQUIDITY_INSUFFICIENT_ACTION', 'reject')

        self._epsilon = Decimal("0.00000001")

    def validate_liquidity(
        self,
        ticker: Dict[str, Any],
        order_amount: float,
        order_price: float,
        is_buy: bool
    ) -> Tuple[bool, str, Dict]:
        """
        验证订单流动性

        Args:
            ticker: 行情数据（包含bid/ask）
            order_amount: 订单数量
            order_price: 订单价格
            is_buy: 是否买入

        Returns:
            (是否通过, 原因, 详细信息)
        """
        if not self.enabled:
            return True, "流动性验证未启用", {}

        details = {
            'order_amount': order_amount,
            'order_value_usdt': order_amount * order_price,
            'is_buy': is_buy,
        }

        try:
            # 1. 检查ticker数据有效性
            if not ticker:
                return False, "行情数据缺失", details

            # 2. 获取对手盘价格和深度
            if is_buy:
                # 买入时检查卖盘（ask）
                counterparty_price = ticker.get('ask')
                # 注意：ccxt的ticker可能没有深度信息，需要从orderbook获取
                # 这里先用简化版本，只检查价格
                if not counterparty_price:
                    return False, "卖盘价格缺失", details

                details['ask_price'] = counterparty_price
            else:
                # 卖出时检查买盘（bid）
                counterparty_price = ticker.get('bid')
                if not counterparty_price:
                    return False, "买盘价格缺失", details

                details['bid_price'] = counterparty_price

            # 3. 计算订单价值（USDT）
            order_value_usdt = order_amount * order_price

            # 4. 检查最小绝对深度（简化版：假设对手盘至少有订单价值的N倍）
            required_depth_usdt = max(
                order_value_usdt * self.depth_multiplier,
                self.min_depth_usdt
            )

            details['required_depth_usdt'] = required_depth_usdt

            # 注意：由于ticker通常不包含深度信息，这里只做基础检查
            # 如果需要精确的深度验证，需要调用fetch_order_book获取完整订单簿

            # 5. 检查价差（作为流动性的间接指标）
            bid = ticker.get('bid', 0)
            ask = ticker.get('ask', 0)

            if bid > 0 and ask > 0:
                spread_pct = (ask - bid) / bid * 100
                details['spread_pct'] = spread_pct

                # 如果价差过大（>1%），可能流动性不足
                if spread_pct > 1.0:
                    logger.warning(f"⚠️ 价差过大: {spread_pct:.2f}%，可能流动性不足")
                    if self.insufficient_action == 'reject':
                        return False, f"价差过大({spread_pct:.2f}%)，流动性可能不足", details

            # 6. 通过验证
            return True, "流动性验证通过", details

        except Exception as e:
            logger.error(f"流动性验证异常: {e}")
            return False, f"流动性验证异常: {e}", details

    def validate_with_orderbook(
        self,
        orderbook: Dict[str, Any],
        order_amount: float,
        order_price: float,
        is_buy: bool
    ) -> Tuple[bool, str, Dict]:
        """
        使用完整订单簿验证流动性（精确版本）

        Args:
            orderbook: 订单簿数据 {'bids': [[price, amount], ...], 'asks': [...]}
            order_amount: 订单数量
            order_price: 订单价格
            is_buy: 是否买入

        Returns:
            (是否通过, 原因, 详细信息)
        """
        if not self.enabled:
            return True, "流动性验证未启用", {}

        details = {
            'order_amount': order_amount,
            'order_value_usdt': order_amount * order_price,
            'is_buy': is_buy,
        }

        try:
            # 1. 检查订单簿有效性
            if not orderbook:
                return False, "订单簿数据缺失", details

            # 2. 获取对手盘
            if is_buy:
                # 买入时检查卖盘（asks）
                levels = orderbook.get('asks', [])
                side_name = "卖盘"
            else:
                # 卖出时检查买盘（bids）
                levels = orderbook.get('bids', [])
                side_name = "买盘"

            if not levels or len(levels) == 0:
                return False, f"{side_name}无深度", details

            # 3. 计算对手盘可用深度
            # 取最优N档的总量
            total_available = 0
            total_value_usdt = 0
            depth_levels = min(5, len(levels))  # 检查前5档

            for i in range(depth_levels):
                level_price = float(levels[i][0])
                level_amount = float(levels[i][1])
                total_available += level_amount
                total_value_usdt += level_price * level_amount

            details['available_amount'] = total_available
            details['available_value_usdt'] = total_value_usdt
            details['depth_levels_checked'] = depth_levels

            # 4. 检查数量是否充足
            if total_available < order_amount:
                return False, f"{side_name}深度不足: 可用={total_available:.4f}, 需求={order_amount:.4f}", details

            # 5. 检查价值是否充足
            order_value_usdt = order_amount * order_price
            required_value_usdt = max(
                order_value_usdt * self.depth_multiplier,
                self.min_depth_usdt
            )

            details['required_value_usdt'] = required_value_usdt

            if total_value_usdt < required_value_usdt:
                return False, f"{side_name}价值不足: 可用={total_value_usdt:.0f}U, 需求={required_value_usdt:.0f}U", details

            # 6. 通过验证
            logger.debug(f"✅ 流动性充足: {side_name}可用={total_available:.4f}, 价值={total_value_usdt:.0f}U")
            return True, "流动性验证通过", details

        except Exception as e:
            logger.error(f"流动性验证异常: {e}")
            return False, f"流动性验证异常: {e}", details


# 全局单例
_liquidity_validator = None


def get_liquidity_validator() -> LiquidityValidator:
    """获取全局流动性验证器实例"""
    global _liquidity_validator
    if _liquidity_validator is None:
        _liquidity_validator = LiquidityValidator()
    return _liquidity_validator
