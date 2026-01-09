from typing import Optional

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
