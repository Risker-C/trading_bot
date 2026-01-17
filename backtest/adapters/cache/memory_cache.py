"""
内存缓存适配器 - 实现IFeatureCache接口
"""
from typing import Optional, Any, Dict
from functools import lru_cache
import time

from backtest.domain.interfaces import IFeatureCache


class MemoryCache(IFeatureCache):
    """内存LRU缓存适配器"""

    def __init__(self, max_size_mb: int = 100):
        self.max_size_mb = max_size_mb
        self._cache: Dict[str, tuple[Any, Optional[float]]] = {}
        self._size_bytes = 0

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self._cache:
            return None

        value, expire_at = self._cache[key]

        # 检查是否过期
        if expire_at and time.time() > expire_at:
            await self.delete(key)
            return None

        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存"""
        expire_at = time.time() + ttl if ttl else None

        # 简单的大小估算
        import sys
        value_size = sys.getsizeof(value)

        # 检查缓存大小限制
        if self._size_bytes + value_size > self.max_size_mb * 1024 * 1024:
            # 清理最旧的缓存
            await self._evict_oldest()

        self._cache[key] = (value, expire_at)
        self._size_bytes += value_size

    async def delete(self, key: str) -> None:
        """删除缓存"""
        if key in self._cache:
            import sys
            value, _ = self._cache[key]
            self._size_bytes -= sys.getsizeof(value)
            del self._cache[key]

    async def _evict_oldest(self) -> None:
        """清理最旧的缓存项"""
        if not self._cache:
            return

        # 删除第一个键（简单策略）
        key = next(iter(self._cache))
        await self.delete(key)
