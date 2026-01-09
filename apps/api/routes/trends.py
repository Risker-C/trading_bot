from fastapi import APIRouter, Depends

from apps.api.auth import get_current_user
from apps.api.models.trend import Trend
from apps.api.services.trend_service import TrendService

router = APIRouter(prefix="/api", tags=["trends"])
trend_service = TrendService()


@router.get("/trends/latest", response_model=Trend)
async def get_latest_trend(_: dict = Depends(get_current_user)) -> Trend:
    return await trend_service.latest_trend()
