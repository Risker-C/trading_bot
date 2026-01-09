from typing import List

from fastapi import APIRouter, Depends, Query

from apps.api.auth import get_current_user
from apps.api.models.trade import Trade
from apps.api.services.trade_service import TradeService

router = APIRouter(prefix="/api", tags=["trades"])
trade_service = TradeService()


def get_trade_service() -> TradeService:
    return trade_service


@router.get("/trades", response_model=List[Trade])
async def list_trades(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: dict = Depends(get_current_user),
    service: TradeService = Depends(get_trade_service),
) -> List[Trade]:
    return await service.list_trades(limit=limit, offset=offset)
