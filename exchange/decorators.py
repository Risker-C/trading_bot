"""
交易所装饰器 - 错误重试机制
"""
import time
import functools
from utils.logger_utils import get_logger

logger = get_logger("exchange_decorators")


def retry_on_error(max_retries=3, backoff_base=1.0):
    """
    错误重试装饰器

    Args:
        max_retries: 最大重试次数
        backoff_base: 退避基础时间（秒）

    Returns:
        装饰器函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = backoff_base * (2 ** attempt)
                        logger.warning(
                            f"{func.__name__} 失败，{delay:.1f}秒后重试 "
                            f"({attempt+1}/{max_retries}): {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} 重试{max_retries}次后仍失败: {e}"
                        )
                        raise
        return wrapper
    return decorator
