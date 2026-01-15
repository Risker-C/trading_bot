from typing import Any, Dict

from fastapi import APIRouter, Depends

from apps.api.auth import get_current_user
from apps.api.services.decision_service import decision_service

router = APIRouter(prefix="/api", tags=["decisions"])


@router.get("/decisions/status")
async def get_decision_status(_: dict = Depends(get_current_user)) -> Dict[str, Any]:
    return await decision_service.get_status()
