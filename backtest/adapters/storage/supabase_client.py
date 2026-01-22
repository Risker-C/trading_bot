"""
Supabase 客户端统一初始化模块
"""
import os
from supabase import create_client, Client
from typing import Optional

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    获取 Supabase 客户端单例

    环境变量:
        SUPABASE_URL: Supabase 项目 URL
        SUPABASE_SERVICE_ROLE_KEY: Service Role Key (后端使用)

    Returns:
        Supabase Client 实例

    Raises:
        ValueError: 缺少必要的环境变量
    """
    global _supabase_client

    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            raise ValueError(
                "Missing required environment variables: "
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY"
            )

        _supabase_client = create_client(url, key)

    return _supabase_client


def reset_supabase_client():
    """重置客户端单例 (用于测试)"""
    global _supabase_client
    _supabase_client = None
