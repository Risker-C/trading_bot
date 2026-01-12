from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from apps.api.auth import get_current_user
from apps.api.services.statistics_service import StatisticsService

router = APIRouter(prefix="/api/statistics", tags=["statistics"])
statistics_service = StatisticsService()


@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_statistics(_: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """获取日统计数据"""
    return await statistics_service.get_daily_statistics()


@router.get("/weekly", response_model=Dict[str, Any])
async def get_weekly_statistics(_: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """获取周统计数据"""
    return await statistics_service.get_weekly_statistics()


@router.get("/monthly", response_model=Dict[str, Any])
async def get_monthly_statistics(_: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """获取月统计数据"""
    return await statistics_service.get_monthly_statistics()


@router.get("/strategy-comparison", response_model=List[Dict[str, Any]])
async def get_strategy_comparison(
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    _: dict = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """获取策略对比数据"""
    return await statistics_service.get_strategy_comparison(start_date=start_date, end_date=end_date)
