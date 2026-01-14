"""
交易所管理器 - 管理多个交易所实例
"""
from typing import Dict, Optional
from utils.logger_utils import get_logger
from .factory import ExchangeFactory
from .interface import ExchangeInterface
from .errors import ExchangeError

logger = get_logger("exchange_manager")


class ExchangeManager:
    """交易所管理器（单例模式）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._exchanges: Dict[str, ExchangeInterface] = {}
        self._current_exchange_name: Optional[str] = None
        self._config: Dict = {}

    def initialize(self, exchanges_config: Dict = None, active_exchange: str = None):
        """初始化管理器

        Args:
            exchanges_config: 交易所配置字典，如果为None则从config.py导入
            active_exchange: 当前激活的交易所名称
        """
        if exchanges_config is None:
            # 从config.py导入配置
            import config
            exchanges_config = config.EXCHANGES_CONFIG
            active_exchange = active_exchange or config.ACTIVE_EXCHANGE

        self._config = exchanges_config
        self._current_exchange_name = active_exchange.lower()

        logger.info(f"初始化交易所管理器，当前交易所: {self._current_exchange_name}")

        # 创建当前激活的交易所实例
        self._create_exchange(self._current_exchange_name)

    def _create_exchange(self, exchange_name: str) -> ExchangeInterface:
        """创建交易所实例

        Args:
            exchange_name: 交易所名称

        Returns:
            交易所实例

        Raises:
            ExchangeError: 配置中未找到交易所
        """
        name = exchange_name.lower()

        if name in self._exchanges:
            return self._exchanges[name]

        if name not in self._config:
            raise ExchangeError(f"配置中未找到交易所: {exchange_name}")

        config = self._config[name]
        exchange = ExchangeFactory.get_or_create(name, config)
        self._exchanges[name] = exchange

        logger.info(f"创建交易所实例: {exchange_name}")
        return exchange

    def get_current_exchange(self) -> ExchangeInterface:
        """获取当前激活的交易所

        Returns:
            当前交易所实例

        Raises:
            ExchangeError: 管理器未初始化
        """
        if self._current_exchange_name is None:
            raise ExchangeError("交易所管理器未初始化")

        return self._exchanges[self._current_exchange_name]

    def get_exchange(self, exchange_name: str) -> ExchangeInterface:
        """获取指定交易所

        Args:
            exchange_name: 交易所名称

        Returns:
            交易所实例
        """
        name = exchange_name.lower()

        if name not in self._exchanges:
            self._create_exchange(name)

        return self._exchanges[name]

    def switch_exchange(self, exchange_name: str) -> bool:
        """切换当前交易所

        Args:
            exchange_name: 交易所名称

        Returns:
            是否切换成功
        """
        name = exchange_name.lower()

        if name not in self._config:
            logger.error(f"切换失败：配置中未找到交易所 {exchange_name}")
            return False

        # 创建新交易所实例（如果不存在）
        try:
            self._create_exchange(name)
            self._current_exchange_name = name
            logger.info(f"切换到交易所: {exchange_name}")
            return True
        except Exception as e:
            logger.error(f"切换交易所失败: {exchange_name}, 错误: {e}")
            return False

    def get_all_exchanges(self) -> Dict[str, ExchangeInterface]:
        """获取所有交易所实例

        Returns:
            交易所实例字典
        """
        return self._exchanges.copy()

    def disconnect_all(self):
        """断开所有交易所连接"""
        for name, exchange in self._exchanges.items():
            try:
                if exchange.is_connected():
                    exchange.disconnect()
                    logger.info(f"断开交易所连接: {name}")
            except Exception as e:
                logger.warning(f"断开交易所连接失败: {name}, 错误: {e}")

        self._exchanges.clear()
        ExchangeFactory.clear_instances()
