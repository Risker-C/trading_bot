from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.auth import get_current_user
from apps.api.services.ai_service import AIService

router = APIRouter(prefix="/api/ai", tags=["ai"])
ai_service = AIService()


class ChatRequest(BaseModel):
    message: str
    market_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    context: Dict[str, Any]
    timestamp: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    _: dict = Depends(get_current_user),
) -> ChatResponse:
    try:
        result = await ai_service.chat(payload.message, payload.market_context)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ChatResponse(**result)
