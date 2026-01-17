"""
接口抽象层 - 支持后续平滑升级到微服务
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import pandas as pd


class IDataRepository(ABC):
    """数据存储接口"""

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int
    ) -> pd.DataFrame:
        """获取K线数据"""
        pass

    @abstractmethod
    async def save_kline_dataset(
        self,
        symbol: str,
        timeframe: str,
        start_ts: int,
        end_ts: int,
        data: bytes
    ) -> str:
        """保存K线数据集（压缩）"""
        pass

    @abstractmethod
    async def create_backtest_run(self, params: Dict[str, Any]) -> str:
        """创建回测运行"""
        pass

    @abstractmethod
    async def update_run_status(self, run_id: str, status: str) -> None:
        """更新运行状态"""
        pass

    @abstractmethod
    async def save_metrics(self, run_id: str, metrics: Dict[str, Any]) -> None:
        """保存回测指标"""
        pass


class IFeatureCache(ABC):
    """特征缓存接口"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除缓存"""
        pass


class ITaskQueue(ABC):
    """任务队列接口"""

    @abstractmethod
    async def enqueue(self, task_type: str, params: Dict[str, Any]) -> str:
        """入队任务"""
        pass

    @abstractmethod
    async def get_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        pass

    @abstractmethod
    async def cancel(self, task_id: str) -> None:
        """取消任务"""
        pass
