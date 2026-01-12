from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from apps.api.auth import get_current_user
from apps.api.models.position import Position
from apps.api.services.position_service import PositionService

router = APIRouter(prefix="/api", tags=["positions"])
position_service = PositionService()


@router.get("/positions/current", response_model=Optional[Position])
async def get_current_position(
    symbol: Optional[str] = Query(default=None),
    _: dict = Depends(get_current_user),
) -> Optional[Position]:
    return await position_service.get_current_position(symbol=symbol)


@router.get("/positions/history", response_model=List[Position])
async def get_position_history(
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    start_date: Optional[str] = Query(default=None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date (YYYY-MM-DD)"),
    _: dict = Depends(get_current_user),
) -> List[Position]:
    """获取持仓历史快照列表"""
    return await position_service.get_position_history(
        symbol=symbol,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date
    )
