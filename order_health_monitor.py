"""
订单健康监控器 (Order Health Monitor)
后台监控订单状态，检测并处理异常订单
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import time

import config
from logger_utils import get_logger, db

logger = get_logger("order_health_monitor")


@dataclass
class OrderHealthInfo:
    """订单健康信息"""
    order_id: str
    symbol: str
    side: str
    status: str
    create_time: datetime
    last_check_time: datetime
    age_seconds: float
    is_stale: bool
    is_partial: bool


class OrderHealthMonitor:
    """订单健康监控器"""

    def __init__(self, trader):
        self.trader = trader
        self.enabled = getattr(config, 'ORDER_HEALTH_CHECK_ENABLED', True)
        self.check_interval = getattr(config, 'ORDER_HEALTH_CHECK_INTERVAL', 300)  # 5分钟
        self.max_age_seconds = getattr(config, 'ORDER_MAX_AGE_SECONDS', 3600)  # 1小时
        self.stale_threshold = getattr(config, 'ORDER_STALE_THRESHOLD_SECONDS', 600)  # 10分钟

        # 跟踪的订单
        self.tracked_orders: Dict[str, OrderHealthInfo] = {}
        self.last_check_time = datetime.now()

        # 统计信息
        self.stats = {
            'total_checks': 0,
            'stale_orders_found': 0,
            'partial_fills_found': 0,
            'orders_cleaned': 0,
        }

    def check_health(self) -> Dict:
        """
        执行健康检查

        Returns:
            检查结果统计
        """
        if not self.enabled:
            return {'enabled': False}

        now = datetime.now()
        elapsed = (now - self.last_check_time).total_seconds()

        if elapsed < self.check_interval:
            return {'skipped': True, 'reason': f'间隔未到({elapsed:.0f}s < {self.check_interval}s)'}

        self.stats['total_checks'] += 1
        self.last_check_time = now

        try:
            # 获取所有开放订单
            open_orders = self._fetch_open_orders()

            if not open_orders:
                logger.debug("无开放订单需要检查")
                return {'open_orders': 0}

            # 检查每个订单
            results = {
                'open_orders': len(open_orders),
                'stale_orders': [],
                'partial_fills': [],
                'aged_orders': [],
            }

            for order in open_orders:
                order_id = order.get('id')
                if not order_id:
                    continue

                health_info = self._check_order_health(order)

                # 更新跟踪信息
                self.tracked_orders[order_id] = health_info

                # 分类问题订单
                if health_info.is_stale:
                    results['stale_orders'].append(order_id)
                    self.stats['stale_orders_found'] += 1

                if health_info.is_partial:
                    results['partial_fills'].append(order_id)
                    self.stats['partial_fills_found'] += 1

                if health_info.age_seconds > self.max_age_seconds:
                    results['aged_orders'].append(order_id)

            # 处理问题订单
            self._handle_problem_orders(results)

            # 清理已关闭的订单
            self._cleanup_tracked_orders(open_orders)

            logger.info(
                f"✅ 订单健康检查完成: "
                f"开放订单={results['open_orders']}, "
                f"过期订单={len(results['stale_orders'])}, "
                f"部分成交={len(results['partial_fills'])}, "
                f"超龄订单={len(results['aged_orders'])}"
            )

            return results

        except Exception as e:
            logger.error(f"订单健康检查失败: {e}")
            return {'error': str(e)}

    def _fetch_open_orders(self) -> List[Dict]:
        """获取所有开放订单"""
        try:
            if not self.trader.exchange:
                return []

            orders = self.trader.exchange.fetch_open_orders(
                symbol=config.SYMBOL,
                params={"productType": config.PRODUCT_TYPE}
            )
            return orders if orders else []

        except Exception as e:
            logger.error(f"获取开放订单失败: {e}")
            return []

    def _check_order_health(self, order: Dict) -> OrderHealthInfo:
        """
        检查单个订单健康状态

        Args:
            order: 订单信息

        Returns:
            订单健康信息
        """
        order_id = order.get('id', '')
        symbol = order.get('symbol', '')
        side = order.get('side', '')
        status = order.get('status', '')
        timestamp = order.get('timestamp', 0)

        # 计算订单年龄
        create_time = datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()
        now = datetime.now()
        age_seconds = (now - create_time).total_seconds()

        # 检查是否过期
        is_stale = age_seconds > self.stale_threshold

        # 检查是否部分成交
        filled = order.get('filled', 0)
        amount = order.get('amount', 0)
        is_partial = 0 < filled < amount

        return OrderHealthInfo(
            order_id=order_id,
            symbol=symbol,
            side=side,
            status=status,
            create_time=create_time,
            last_check_time=now,
            age_seconds=age_seconds,
            is_stale=is_stale,
            is_partial=is_partial
        )

    def _handle_problem_orders(self, results: Dict) -> None:
        """
        处理问题订单

        Args:
            results: 检查结果
        """
        # 处理超龄订单
        for order_id in results['aged_orders']:
            logger.warning(f"⚠️ 发现超龄订单: {order_id}, 年龄>{self.max_age_seconds}秒")
            self._cancel_order(order_id, reason="超龄")

        # 处理过期订单
        for order_id in results['stale_orders']:
            if order_id not in results['aged_orders']:  # 避免重复处理
                logger.warning(f"⚠️ 发现过期订单: {order_id}, 年龄>{self.stale_threshold}秒")
                # 过期订单可以选择取消或继续等待
                # 这里选择记录但不取消，让超龄逻辑处理

        # 处理部分成交订单
        for order_id in results['partial_fills']:
            health_info = self.tracked_orders.get(order_id)
            if health_info:
                logger.info(
                    f"ℹ️ 部分成交订单: {order_id}, "
                    f"方向={health_info.side}, "
                    f"年龄={health_info.age_seconds:.0f}秒"
                )

    def _cancel_order(self, order_id: str, reason: str = "") -> bool:
        """
        取消订单

        Args:
            order_id: 订单ID
            reason: 取消原因

        Returns:
            是否成功
        """
        try:
            logger.info(f"🚫 取消订单: {order_id}, 原因: {reason}")
            self.trader.cancel_order(order_id)
            self.stats['orders_cleaned'] += 1
            return True

        except Exception as e:
            logger.error(f"取消订单失败 {order_id}: {e}")
            return False

    def _cleanup_tracked_orders(self, open_orders: List[Dict]) -> None:
        """
        清理已关闭的订单

        Args:
            open_orders: 当前开放订单列表
        """
        open_order_ids = {order.get('id') for order in open_orders if order.get('id')}
        tracked_order_ids = set(self.tracked_orders.keys())

        # 找出已关闭的订单
        closed_order_ids = tracked_order_ids - open_order_ids

        for order_id in closed_order_ids:
            del self.tracked_orders[order_id]

        if closed_order_ids:
            logger.debug(f"清理 {len(closed_order_ids)} 个已关闭订单的跟踪信息")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'tracked_orders': len(self.tracked_orders),
            'last_check_time': self.last_check_time.strftime('%Y-%m-%d %H:%M:%S'),
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            'total_checks': 0,
            'stale_orders_found': 0,
            'partial_fills_found': 0,
            'orders_cleaned': 0,
        }
        logger.info("订单健康监控统计已重置")


# 全局单例
_order_health_monitor = None


def get_order_health_monitor(trader) -> OrderHealthMonitor:
    """获取全局订单健康监控器实例"""
    global _order_health_monitor
    if _order_health_monitor is None:
        _order_health_monitor = OrderHealthMonitor(trader)
    return _order_health_monitor
