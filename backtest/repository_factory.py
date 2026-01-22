"""
Repository Factory - 根据环境变量选择存储后端
"""
import os
from typing import Optional
from backtest.repository import BacktestRepository as SQLiteBacktestRepository
from backtest.summary_repository import SummaryRepository as SQLiteSummaryRepository
from backtest.ai_repository import AIReportRepository, SupabaseAIReportRepository
from backtest.adapters.storage.supabase_repo import SupabaseBacktestRepository
from backtest.adapters.storage.supabase_summary_repo import SupabaseSummaryRepository


def get_backtest_repository():
    """
    获取 Backtest Repository 实例

    根据环境变量 USE_SUPABASE 选择实现:
    - USE_SUPABASE=true: 使用 Supabase
    - 其他: 使用 SQLite (默认)

    Returns:
        BacktestRepository 实例
    """
    use_supabase = os.getenv('USE_SUPABASE', 'false').lower() == 'true'

    if use_supabase:
        return SupabaseBacktestRepository()
    else:
        return SQLiteBacktestRepository()


def get_summary_repository(db_path: Optional[str] = None):
    """
    获取 Summary Repository 实例

    根据环境变量 USE_SUPABASE 选择实现:
    - USE_SUPABASE=true: 使用 Supabase
    - 其他: 使用 SQLite (默认)

    Returns:
        SummaryRepository 实例
    """
    use_supabase = os.getenv('USE_SUPABASE', 'false').lower() == 'true'

    if use_supabase:
        return SupabaseSummaryRepository()
    if db_path:
        return SQLiteSummaryRepository(db_path)
    return SQLiteSummaryRepository()


def get_ai_report_repository(db_path: Optional[str] = None):
    """
    获取 AI Report Repository 实例

    根据环境变量 USE_SUPABASE 选择实现:
    - USE_SUPABASE=true: 使用 Supabase
    - 其他: 使用 SQLite (默认)
    """
    use_supabase = os.getenv('USE_SUPABASE', 'false').lower() == 'true'

    if use_supabase:
        return SupabaseAIReportRepository()
    if db_path:
        return AIReportRepository(db_path)
    return AIReportRepository()
