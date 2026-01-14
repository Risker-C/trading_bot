"""
错误退避控制器 (Error Backoff Controller)
实现指数退避机制，防止API错误级联失败
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple
import time
import config
from utils.logger_utils import get_logger

logger = get_logger("error_backoff")


class ErrorType(Enum):
    """错误类型枚举"""
    RATE_LIMIT = "429"              # 速率限制
    INVALID_NONCE = "21104"         # 无效nonce (Bitget特定)
    NETWORK_ERROR = "network"       # 网络错误
    API_ERROR = "api"               # 通用API错误
    TIMEOUT = "timeout"             # 超时错误


@dataclass
class BackoffState:
    """退避状态"""
    exchange: str                    # 交易所名称
    error_type: ErrorType           # 错误类型
    error_count: int                # 连续错误计数
    last_error_time: datetime       # 最后错误时间
    pause_until: datetime           # 暂停直到此时间
    pause_duration_seconds: float   # 当前暂停时长
    recovery_logged: bool = False   # 是否已记录恢复日志


class ErrorBackoffController:
    """错误退避控制器"""

    def __init__(self):
        self._backoff_states: Dict[str, BackoffState] = {}
        self._log_throttle: Dict[str, float] = {}  # 日志节流

    def register_error(
        self,
        exchange: str,
        error_code: str,
        error_message: str = ""
    ) -> None:
        """
        注册错误并触发退避

        Args:
            exchange: 交易所名称
            error_code: 错误代码
            error_message: 错误消息
        """
        error_type = self._parse_error_type(error_code)
        now = datetime.now()

        if exchange in self._backoff_states:
            state = self._backoff_states[exchange]

            # 检查是否需要重置错误计数
            time_since_last_error = (now - state.last_error_time).total_seconds()
            if time_since_last_error > config.ERROR_RESET_SECONDS:
                # 超过重置时间，重置计数
                state.error_count = 1
                state.pause_duration_seconds = config.ERROR_BACKOFF_MIN_SECONDS
            else:
                # 增加错误计数并计算新的退避时间
                state.error_count += 1
                state.pause_duration_seconds = min(
                    config.ERROR_BACKOFF_MIN_SECONDS * (config.ERROR_BACKOFF_MULTIPLIER ** (state.error_count - 1)),
                    config.ERROR_BACKOFF_MAX_SECONDS
                )

            state.error_type = error_type
            state.last_error_time = now
            state.pause_until = now + timedelta(seconds=state.pause_duration_seconds)
            state.recovery_logged = False
        else:
            # 首次错误
            pause_duration = config.ERROR_BACKOFF_MIN_SECONDS
            self._backoff_states[exchange] = BackoffState(
                exchange=exchange,
                error_type=error_type,
                error_count=1,
                last_error_time=now,
                pause_until=now + timedelta(seconds=pause_duration),
                pause_duration_seconds=pause_duration,
                recovery_logged=False
            )

        state = self._backoff_states[exchange]
        logger.warning(
            f"⚠️ 错误退避触发 [{exchange}] "
            f"错误类型: {error_type.value}, "
            f"错误计数: {state.error_count}, "
            f"暂停时长: {state.pause_duration_seconds:.0f}秒, "
            f"恢复时间: {state.pause_until.strftime('%H:%M:%S')}"
        )

        if error_message:
            logger.debug(f"错误详情: {error_message}")

    def is_paused(self, exchange: str) -> bool:
        """
        检查交易所是否处于暂停状态

        Args:
            exchange: 交易所名称

        Returns:
            是否暂停
        """
        if exchange not in self._backoff_states:
            return False

        state = self._backoff_states[exchange]
        now = datetime.now()

        if now < state.pause_until:
            # 仍在暂停期
            self._log_throttled(
                f"paused_{exchange}",
                f"⏸️ 交易暂停中 [{exchange}] "
                f"剩余: {(state.pause_until - now).total_seconds():.0f}秒, "
                f"恢复时间: {state.pause_until.strftime('%H:%M:%S')}",
                interval_seconds=60
            )
            return True
        else:
            # 暂停期已过
            if not state.recovery_logged:
                logger.info(
                    f"✅ 交易恢复 [{exchange}] "
                    f"错误计数: {state.error_count}, "
                    f"保持状态以备后续指数退避"
                )
                state.recovery_logged = True
            return False

    def get_pause_info(self, exchange: str) -> Optional[Tuple[str, int, datetime]]:
        """
        获取暂停信息

        Args:
            exchange: 交易所名称

        Returns:
            (错误原因, 剩余秒数, 恢复时间) 或 None
        """
        if exchange not in self._backoff_states:
            return None

        state = self._backoff_states[exchange]
        now = datetime.now()

        if now < state.pause_until:
            remaining_seconds = int((state.pause_until - now).total_seconds())
            return (
                f"{state.error_type.value} (错误{state.error_count}次)",
                remaining_seconds,
                state.pause_until
            )
        return None

    def reset_exchange(self, exchange: str) -> None:
        """
        手动重置交易所退避状态

        Args:
            exchange: 交易所名称
        """
        if exchange in self._backoff_states:
            del self._backoff_states[exchange]
            logger.info(f"🔄 已重置退避状态 [{exchange}]")

    def get_all_paused_exchanges(self) -> Dict[str, str]:
        """
        获取所有暂停的交易所

        Returns:
            {交易所名称: 暂停原因}
        """
        paused = {}
        now = datetime.now()

        for exchange, state in self._backoff_states.items():
            if now < state.pause_until:
                paused[exchange] = f"{state.error_type.value} (错误{state.error_count}次)"

        return paused

    def _parse_error_type(self, error_code: str) -> ErrorType:
        """
        解析错误代码到错误类型

        Args:
            error_code: 错误代码

        Returns:
            错误类型
        """
        error_code_str = str(error_code).lower()

        if "429" in error_code_str or "rate" in error_code_str:
            return ErrorType.RATE_LIMIT
        elif "21104" in error_code_str or "nonce" in error_code_str:
            return ErrorType.INVALID_NONCE
        elif "timeout" in error_code_str:
            return ErrorType.TIMEOUT
        elif "network" in error_code_str or "connection" in error_code_str:
            return ErrorType.NETWORK_ERROR
        else:
            return ErrorType.API_ERROR

    def _log_throttled(
        self,
        key: str,
        message: str,
        interval_seconds: float = 60
    ) -> None:
        """
        节流日志输出

        Args:
            key: 日志键
            message: 日志消息
            interval_seconds: 节流间隔（秒）
        """
        now = time.time()
        last_log_time = self._log_throttle.get(key, 0)

        if now - last_log_time >= interval_seconds:
            logger.info(message)
            self._log_throttle[key] = now


# 全局单例
_backoff_controller = None


def get_backoff_controller() -> ErrorBackoffController:
    """获取全局退避控制器实例"""
    global _backoff_controller
    if _backoff_controller is None:
        _backoff_controller = ErrorBackoffController()
    return _backoff_controller
