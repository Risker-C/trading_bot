from typing import List

from fastapi import APIRouter, Depends, Query

from apps.api.auth import get_current_user
from apps.api.models.trend import Trend
from apps.api.services.trend_service import TrendService

router = APIRouter(prefix="/api", tags=["trends"])
trend_service = TrendService()


@router.get("/trends/latest", response_model=Trend)
async def get_latest_trend(_: dict = Depends(get_current_user)) -> Trend:
    return await trend_service.latest_trend()


@router.get("/trends/history", response_model=List[Trend])
async def get_trend_history(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: dict = Depends(get_current_user),
) -> List[Trend]:
    """获取趋势历史数据（基于历史交易记录）"""
    return await trend_service.get_trend_history(limit=limit, offset=offset)
