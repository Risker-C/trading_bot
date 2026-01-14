"""
跨交易所持仓追踪器 - 持仓管理和净敞口计算
"""
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from utils.logger_utils import get_logger
from exchange.manager import ExchangeManager

logger = get_logger("position_tracker")


class CrossExchangePositionTracker:
    """跨交易所持仓追踪器"""

    def __init__(self, exchange_manager: ExchangeManager, config: Dict):
        """
        初始化持仓追踪器

        Args:
            exchange_manager: 交易所管理器
            config: 配置字典
        """
        self.exchange_manager = exchange_manager
        self.config = config

        # 持仓追踪
        self.positions: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        # 格式: {exchange_name: {symbol: quantity}}

        # 持仓历史
        self.position_history: List[Dict] = []

        # 配置参数
        self.symbol = config.get("symbol", "BTCUSDT")
        self.exchanges = config.get("exchanges", ["bitget", "binance", "okx"])

        logger.info(f"持仓追踪器初始化: symbol={self.symbol}, exchanges={self.exchanges}")

    def update_position(self, exchange_name: str, symbol: str,
                       quantity_change: float, side: str):
        """
        更新持仓

        Args:
            exchange_name: 交易所名称
            symbol: 交易对
            quantity_change: 数量变化
            side: 方向 (buy/sell)
        """
        try:
            # 买入增加持仓，卖出减少持仓
            if side.lower() == "buy":
                self.positions[exchange_name][symbol] += quantity_change
            elif side.lower() == "sell":
                self.positions[exchange_name][symbol] -= quantity_change

            # 记录历史
            self.position_history.append({
                "timestamp": datetime.now(),
                "exchange": exchange_name,
                "symbol": symbol,
                "quantity_change": quantity_change if side.lower() == "buy" else -quantity_change,
                "side": side,
                "new_position": self.positions[exchange_name][symbol]
            })

            logger.debug(f"持仓更新: {exchange_name} {symbol} {side} {quantity_change:.6f}, "
                        f"new_position={self.positions[exchange_name][symbol]:.6f}")

        except Exception as e:
            logger.error(f"持仓更新失败: {e}", exc_info=True)

    def get_position(self, exchange_name: str, symbol: str) -> float:
        """
        获取持仓

        Args:
            exchange_name: 交易所名称
            symbol: 交易对

        Returns:
            持仓数量
        """
        return self.positions.get(exchange_name, {}).get(symbol, 0.0)

    def get_all_positions(self) -> Dict[str, Dict[str, float]]:
        """
        获取所有持仓

        Returns:
            所有持仓字典
        """
        return dict(self.positions)

    def get_net_exposure(self, symbol: Optional[str] = None) -> Dict[str, float]:
        """
        计算净敞口

        Args:
            symbol: 交易对（如果为None，计算所有交易对）

        Returns:
            净敞口字典 {symbol: net_quantity}
        """
        net_exposure = defaultdict(float)

        try:
            if symbol:
                # 计算指定交易对的净敞口
                for exchange_name in self.exchanges:
                    position = self.get_position(exchange_name, symbol)
                    net_exposure[symbol] += position
            else:
                # 计算所有交易对的净敞口
                for exchange_name in self.exchanges:
                    for sym, quantity in self.positions.get(exchange_name, {}).items():
                        net_exposure[sym] += quantity

            logger.debug(f"净敞口计算: {dict(net_exposure)}")
            return dict(net_exposure)

        except Exception as e:
            logger.error(f"净敞口计算失败: {e}", exc_info=True)
            return {}

    def reconcile_positions(self, symbol: Optional[str] = None) -> Dict[str, Dict]:
        """
        对账持仓（与交易所实际余额对比）

        Args:
            symbol: 交易对（如果为None，对账所有交易对）

        Returns:
            对账结果 {exchange: {symbol: {tracked: x, actual: y, diff: z}}}
        """
        reconciliation_result = {}

        try:
            for exchange_name in self.exchanges:
                exchange = self.exchange_manager.get_exchange(exchange_name)
                reconciliation_result[exchange_name] = {}

                # 获取实际余额
                try:
                    balance = exchange.get_balance()

                    # 对比追踪的持仓和实际余额
                    if symbol:
                        tracked_position = self.get_position(exchange_name, symbol)
                        # 注意: 这里简化处理，实际应该查询具体币种余额
                        reconciliation_result[exchange_name][symbol] = {
                            "tracked": tracked_position,
                            "actual": balance,  # 简化处理
                            "diff": balance - tracked_position
                        }
                    else:
                        # 对账所有持仓
                        for sym, tracked_qty in self.positions.get(exchange_name, {}).items():
                            reconciliation_result[exchange_name][sym] = {
                                "tracked": tracked_qty,
                                "actual": balance,  # 简化处理
                                "diff": balance - tracked_qty
                            }

                except Exception as e:
                    logger.error(f"获取 {exchange_name} 余额失败: {e}")
                    reconciliation_result[exchange_name]["error"] = str(e)

            logger.info(f"持仓对账完成: {len(reconciliation_result)} 个交易所")
            return reconciliation_result

        except Exception as e:
            logger.error(f"持仓对账失败: {e}", exc_info=True)
            return {}

    def get_position_report(self) -> Dict:
        """
        生成持仓报告

        Returns:
            持仓报告字典
        """
        try:
            report = {
                "timestamp": datetime.now(),
                "exchanges": {},
                "net_exposure": {},
                "total_positions": 0,
                "position_count": 0
            }

            # 统计各交易所持仓
            for exchange_name in self.exchanges:
                exchange_positions = self.positions.get(exchange_name, {})
                if exchange_positions:
                    report["exchanges"][exchange_name] = dict(exchange_positions)
                    report["position_count"] += len(exchange_positions)

            # 计算净敞口
            report["net_exposure"] = self.get_net_exposure()

            # 计算总持仓数量
            for sym, net_qty in report["net_exposure"].items():
                report["total_positions"] += abs(net_qty)

            logger.debug(f"持仓报告生成: {report['position_count']} 个持仓, "
                        f"净敞口={report['total_positions']:.6f}")

            return report

        except Exception as e:
            logger.error(f"生成持仓报告失败: {e}", exc_info=True)
            return {}

    def clear_positions(self):
        """清空所有持仓记录"""
        self.positions.clear()
        logger.info("持仓记录已清空")

    def get_position_history(self, limit: Optional[int] = None) -> List[Dict]:
        """
        获取持仓历史

        Args:
            limit: 限制返回数量

        Returns:
            持仓历史列表
        """
        if limit:
            return self.position_history[-limit:]
        return self.position_history
