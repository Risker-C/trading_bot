import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

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
    """WebSocket 连接管理器，支持频道订阅"""

    # 支持的频道列表
    AVAILABLE_CHANNELS = ["trades", "positions", "trends", "indicators"]

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        # 存储每个连接的订阅频道，默认订阅所有频道（向后兼容）
        self.subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        """连接 WebSocket 并初始化订阅（默认订阅所有频道）"""
        await websocket.accept()
        self.active_connections.add(websocket)
        # 默认订阅所有频道（向后兼容）
        self.subscriptions[websocket] = set(self.AVAILABLE_CHANNELS)

    def disconnect(self, websocket: WebSocket) -> None:
        """断开 WebSocket 连接并清理订阅"""
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)

    def subscribe(self, websocket: WebSocket, channels: List[str]) -> List[str]:
        """
        订阅频道

        Args:
            websocket: WebSocket 连接
            channels: 要订阅的频道列表

        Returns:
            成功订阅的频道列表
        """
        if websocket not in self.subscriptions:
            self.subscriptions[websocket] = set()

        # 只订阅有效的频道
        valid_channels = [ch for ch in channels if ch in self.AVAILABLE_CHANNELS]
        self.subscriptions[websocket].update(valid_channels)
        return valid_channels

    def unsubscribe(self, websocket: WebSocket, channels: List[str]) -> List[str]:
        """
        取消订阅频道

        Args:
            websocket: WebSocket 连接
            channels: 要取消订阅的频道列表

        Returns:
            成功取消订阅的频道列表
        """
        if websocket not in self.subscriptions:
            return []

        valid_channels = [ch for ch in channels if ch in self.AVAILABLE_CHANNELS]
        self.subscriptions[websocket].difference_update(valid_channels)
        return valid_channels

    def get_subscriptions(self, websocket: WebSocket) -> Set[str]:
        """获取连接的订阅频道"""
        return self.subscriptions.get(websocket, set())

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """发送消息给指定连接"""
        await websocket.send_text(json.dumps(message, default=_json_default))


manager = ConnectionManager()


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket, token: Optional[str] = Query(default=None)) -> None:
    """WebSocket 流式推送端点，支持频道订阅"""
    if not _validate_token(token):
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await manager.connect(websocket)
    interval = float(os.getenv("WS_PUSH_INTERVAL", 2))

    try:
        # 创建两个并发任务：接收消息和推送数据
        receive_task = asyncio.create_task(_handle_client_messages(websocket))
        push_task = asyncio.create_task(_push_data_loop(websocket, interval))

        # 等待任何一个任务完成（通常是连接断开）
        done, pending = await asyncio.wait(
            [receive_task, push_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # 取消未完成的任务
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


async def _handle_client_messages(websocket: WebSocket) -> None:
    """处理客户端发送的消息（订阅/取消订阅）"""
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")
            channels = message.get("channels", [])

            if action == "subscribe":
                # 订阅频道
                subscribed = manager.subscribe(websocket, channels)
                response = {
                    "type": "subscribed",
                    "channels": subscribed,
                    "timestamp": datetime.utcnow()
                }
                await manager.send_personal_message(response, websocket)

            elif action == "unsubscribe":
                # 取消订阅频道
                unsubscribed = manager.unsubscribe(websocket, channels)
                response = {
                    "type": "unsubscribed",
                    "channels": unsubscribed,
                    "timestamp": datetime.utcnow()
                }
                await manager.send_personal_message(response, websocket)

            elif action == "ping":
                # 心跳检测
                response = {
                    "type": "pong",
                    "timestamp": datetime.utcnow()
                }
                await manager.send_personal_message(response, websocket)

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        # 忽略无效的 JSON 消息
        pass


async def _push_data_loop(websocket: WebSocket, interval: float) -> None:
    """定期推送数据循环"""
    try:
        while True:
            # 获取当前连接的订阅频道
            subscribed_channels = manager.get_subscriptions(websocket)

            # 根据订阅频道构建数据
            payload = await _build_payload(subscribed_channels)

            # 推送数据
            await manager.send_personal_message(payload, websocket)

            # 等待下一次推送
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
    """
    根据订阅的频道构建数据负载

    Args:
        subscribed_channels: 订阅的频道集合

    Returns:
        包含订阅频道数据的字典
    """
    payload: Dict[str, Any] = {"updated_at": datetime.utcnow()}

    # 创建任务列表，只获取订阅的频道数据
    tasks = {}
    if "trades" in subscribed_channels:
        tasks["trades"] = asyncio.create_task(trade_service.list_trades(limit=5))
    if "positions" in subscribed_channels:
        tasks["positions"] = asyncio.create_task(position_service.get_current_position())
    if "trends" in subscribed_channels:
        tasks["trends"] = asyncio.create_task(trend_service.latest_trend())
    if "indicators" in subscribed_channels:
        tasks["indicators"] = asyncio.create_task(indicator_service.get_active_indicators())

    # 等待所有任务完成
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
        except Exception:
            # 如果某个频道数据获取失败，跳过该频道
            pass

    return payload


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Type {type(value)} is not JSON serializable")
