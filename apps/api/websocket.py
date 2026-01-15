"""
Compatibility shim for backward compatibility.
All WebSocket functionality has been moved to apps.api.routes.stream
"""
from apps.api.routes.stream import (
    ConnectionManager,
    manager,
    router,
    websocket_stream,
)

__all__ = [
    "ConnectionManager",
    "manager",
    "router",
    "websocket_stream",
]
