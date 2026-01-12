from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.get("/trades/{trade_id}", response_model=Trade)
async def get_trade_by_id(
    trade_id: int,
    _: dict = Depends(get_current_user),
    service: TradeService = Depends(get_trade_service),
) -> Trade:
    """获取单个交易详情"""
    trade = await service.get_trade_by_id(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade with id {trade_id} not found")
    return trade
