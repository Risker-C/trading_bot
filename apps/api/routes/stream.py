import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from apps.api.auth import ALGORITHM, SECRET_KEY
from apps.api.services.decision_service import decision_service
from apps.api.services.indicator_service import IndicatorService
from apps.api.services.position_service import PositionService
from apps.api.services.trade_service import TradeService
from apps.api.services.trend_service import TrendService
from apps.api.services.ticker_service import ticker_service
from backtest.repository import BacktestRepository

router = APIRouter()

trade_service = TradeService()
position_service = PositionService()
trend_service = TrendService(trade_service=trade_service)
indicator_service = IndicatorService(trade_service=trade_service)
backtest_repo = BacktestRepository()


class ConnectionManager:
    """WebSocket connection manager with channel subscriptions."""

    AVAILABLE_CHANNELS = ["trades", "positions", "trends", "indicators", "ticker", "decision", "backtest"]

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set(self.AVAILABLE_CHANNELS)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)

    def subscribe(self, websocket: WebSocket, channels: List[str]) -> List[str]:
        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = set()

        valid_channels = [ch for ch in channels if ch in self.AVAILABLE_CHANNELS]
        self.subscriptions[websocket].update(valid_channels)
        return valid_channels

    def unsubscribe(self, websocket: WebSocket, channels: List[str]) -> List[str]:
        if websocket not in self.subscriptions:
            return []

        valid_channels = [ch for ch in channels if ch in self.AVAILABLE_CHANNELS]
        self.subscriptions[websocket].difference_update(valid_channels)
        return valid_channels

    def get_subscriptions(self, websocket: WebSocket) -> Set[str]:
        return self.subscriptions.get(websocket, set())

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
        receive_task = asyncio.create_task(_handle_client_messages(websocket))
        push_task = asyncio.create_task(_push_data_loop(websocket, interval))

        done, pending = await asyncio.wait(
            [receive_task, push_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


async def _handle_client_messages(websocket: WebSocket) -> None:
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")
            channels = message.get("channels", [])

            if action == "subscribe":
                subscribed = manager.subscribe(websocket, channels)
                response = {
                    "type": "subscribed",
                    "channels": subscribed,
                    "timestamp": datetime.utcnow()
                }
                await manager.send_personal_message(response, websocket)

            elif action == "unsubscribe":
                unsubscribed = manager.unsubscribe(websocket, channels)
                response = {
                    "type": "unsubscribed",
                    "channels": unsubscribed,
                    "timestamp": datetime.utcnow()
                }
                await manager.send_personal_message(response, websocket)

            elif action == "ping":
                response = {
                    "type": "pong",
                    "timestamp": datetime.utcnow()
                }
                await manager.send_personal_message(response, websocket)

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        pass


async def _push_data_loop(websocket: WebSocket, interval: float) -> None:
    decision_interval = float(os.getenv("WS_DECISION_INTERVAL", 5))
    decision_cache: Optional[Dict[str, Any]] = None
    last_decision_fetch = 0.0

    try:
        while True:
            subscribed_channels = manager.get_subscriptions(websocket)
            payload = await _build_payload(subscribed_channels)

            if "decision" in subscribed_channels:
                now = time.monotonic()
                if decision_cache is None or (now - last_decision_fetch) >= decision_interval:
                    try:
                        decision_cache = await decision_service.get_status()
                        last_decision_fetch = now
                    except Exception:
                        pass
                if decision_cache is not None:
                    payload["decision"] = decision_cache

            await manager.send_personal_message(payload, websocket)
            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        pass


def _validate_token(token: Optional[str]) -> bool:
    if not token:
        return False
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False


async def _build_payload(subscribed_channels: Set[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"updated_at": datetime.utcnow()}

    tasks = {}
    if "trades" in subscribed_channels:
        tasks["trades"] = asyncio.create_task(trade_service.list_trades(limit=5))
    if "positions" in subscribed_channels:
        tasks["positions"] = asyncio.create_task(position_service.get_current_position())
    if "trends" in subscribed_channels:
        tasks["trends"] = asyncio.create_task(trend_service.latest_trend())
    if "indicators" in subscribed_channels:
        tasks["indicators"] = asyncio.create_task(indicator_service.get_active_indicators())
    if "ticker" in subscribed_channels:
        tasks["ticker"] = asyncio.create_task(ticker_service.get_ticker())
    if "backtest" in subscribed_channels:
        tasks["backtest"] = asyncio.create_task(asyncio.to_thread(_get_backtest_status))

    for channel, task in tasks.items():
        try:
            result = await task
            if channel == "trades":
                payload["trades"] = [trade.model_dump() for trade in result]
            elif channel == "positions":
                payload["position"] = result.model_dump() if result else None
            elif channel == "trends":
                payload["trend"] = result.model_dump()
            elif channel == "indicators":
                payload["indicators"] = [indicator.model_dump() for indicator in result]
            elif channel == "ticker":
                payload["ticker"] = result.model_dump() if result else None
            elif channel == "backtest":
                payload["backtest"] = result
        except Exception:
            pass

    return payload


def _get_backtest_status() -> Optional[Dict[str, Any]]:
    """Get latest running backtest session status"""
    try:
        conn = backtest_repo._get_conn()
        cursor = conn.execute("""
            SELECT id, status, symbol, timeframe, initial_capital, strategy_name, updated_at, error_message
            FROM backtest_sessions
            WHERE status IN ('running', 'created', 'completed', 'failed')
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "session_id": row[0],
            "status": row[1],
            "symbol": row[2],
            "timeframe": row[3],
            "initial_capital": row[4],
            "strategy_name": row[5],
            "updated_at": row[6],
            "error_message": row[7]
        }
    except Exception:
        return None


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Type {type(value)} is not JSON serializable")
