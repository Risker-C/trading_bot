"""
交易所工厂类 - 创建和管理交易所适配器实例
"""
from typing import Dict, Type, Optional
from logger_utils import get_logger
from .interface import ExchangeInterface
from .errors import ExchangeError

logger = get_logger("exchange_factory")


class ExchangeFactory:
    """交易所工厂类"""

    # 注册的适配器类
    _adapters: Dict[str, Type[ExchangeInterface]] = {}

    # 单例缓存
    _instances: Dict[str, ExchangeInterface] = {}

    @classmethod
    def register(cls, name: str, adapter_class: Type[ExchangeInterface]):
        """注册适配器类

        Args:
            name: 交易所名称（如 'bitget', 'binance', 'okx'）
            adapter_class: 适配器类
        """
        cls._adapters[name.lower()] = adapter_class
        logger.info(f"注册交易所适配器: {name}")

    @classmethod
    def create(cls, exchange_name: str, config: Dict) -> ExchangeInterface:
        """创建交易所适配器实例

        Args:
            exchange_name: 交易所名称
            config: 配置字典

        Returns:
            交易所适配器实例

        Raises:
            ExchangeError: 不支持的交易所或创建失败
        """
        name = exchange_name.lower()

        if name not in cls._adapters:
            raise ExchangeError(
                f"不支持的交易所: {exchange_name}. "
                f"支持的交易所: {', '.join(cls._adapters.keys())}"
            )

        adapter_class = cls._adapters[name]
        logger.info(f"创建交易所适配器: {exchange_name}")

        try:
            instance = adapter_class(config)
            return instance
        except Exception as e:
            logger.error(f"创建交易所适配器失败: {exchange_name}, 错误: {e}")
            raise ExchangeError(f"创建交易所适配器失败: {exchange_name}", e)

    @classmethod
    def get_or_create(cls, exchange_name: str, config: Dict) -> ExchangeInterface:
        """获取或创建交易所适配器实例（单例模式）

        Args:
            exchange_name: 交易所名称
            config: 配置字典

        Returns:
            交易所适配器实例
        """
        name = exchange_name.lower()

        if name not in cls._instances:
            cls._instances[name] = cls.create(exchange_name, config)

        return cls._instances[name]

    @classmethod
    def clear_instances(cls):
        """清除所有实例缓存"""
        for name, instance in cls._instances.items():
            try:
                if instance.is_connected():
                    instance.disconnect()
            except Exception as e:
                logger.warning(f"断开交易所连接失败: {name}, 错误: {e}")

        cls._instances.clear()
        logger.info("清除所有交易所实例缓存")

    @classmethod
    def get_supported_exchanges(cls) -> list:
        """获取支持的交易所列表

        Returns:
            支持的交易所名称列表
        """
        return list(cls._adapters.keys())
