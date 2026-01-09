import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from apps.api.auth import ALGORITHM, SECRET_KEY
from apps.api.services.indicator_service import IndicatorService
from apps.api.services.position_service import PositionService
from apps.api.services.trade_service import TradeService
from apps.api.services.trend_service import TrendService

router = APIRouter()

trade_service = TradeService()
position_service = PositionService()
trend_service = TrendService(trade_service=trade_service)
indicator_service = IndicatorService(trade_service=trade_service)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        await websocket.send_text(json.dumps(message, default=_json_default))


manager = ConnectionManager()


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket, token: Optional[str] = Query(default=None)) -> None:
    if not _validate_token(token):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await manager.connect(websocket)
    interval = float(os.getenv("WS_PUSH_INTERVAL", 2))

    try:
        while True:
            payload = await _build_payload()
            await manager.send_personal_message(payload, websocket)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _validate_token(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False


async def _build_payload() -> Dict[str, Any]:
    trades_task = asyncio.create_task(trade_service.list_trades(limit=5))
    position_task = asyncio.create_task(position_service.get_current_position())
    trend_task = asyncio.create_task(trend_service.latest_trend())
    indicators_task = asyncio.create_task(indicator_service.get_active_indicators())

    trades = await trades_task
    position = await position_task
    trend = await trend_task
    indicators = await indicators_task

    return {
        "trades": [trade.model_dump() for trade in trades],
        "position": position.model_dump() if position else None,
        "trend": trend.model_dump(),
        "indicators": [indicator.model_dump() for indicator in indicators],
        "updated_at": datetime.utcnow(),
    }


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Type {type(value)} is not JSON serializable")
