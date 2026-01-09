from fastapi import APIRouter, Depends

from apps.api.auth import get_current_user
from apps.api.models.trade import TradeHistoryResponse
from apps.api.services.trade_service import TradeService

router = APIRouter(prefix="/api", tags=["history"])
trade_service = TradeService()


@router.get("/history", response_model=TradeHistoryResponse)
async def get_history(_: dict = Depends(get_current_user)) -> TradeHistoryResponse:
    return await trade_service.get_history()
