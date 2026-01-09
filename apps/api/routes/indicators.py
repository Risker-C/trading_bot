from typing import List

from fastapi import APIRouter, Depends

from apps.api.auth import get_current_user
from apps.api.models.indicator import Indicator
from apps.api.services.indicator_service import IndicatorService

router = APIRouter(prefix="/api", tags=["indicators"])
indicator_service = IndicatorService()


@router.get("/indicators/active", response_model=List[Indicator])
async def get_active_indicators(_: dict = Depends(get_current_user)) -> List[Indicator]:
    return await indicator_service.get_active_indicators()
