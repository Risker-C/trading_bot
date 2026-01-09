# 交易数据可视化项目 - 后端API设计

**文档版本**: v1.0
**创建时间**: 2026-01-09

---

## 1. API 概览

### 1.1 基础信息

- **Base URL**: `http://localhost:8000` (开发) / `https://api.yourdomain.com` (生产)
- **协议**: HTTP/1.1, WebSocket
- **认证**: JWT Bearer Token
- **数据格式**: JSON
- **字符编码**: UTF-8

### 1.2 API 端点列表

| 端点 | 方法 | 功能 | 认证 |
|------|------|------|------|
| `/api/auth/login` | POST | 用户登录 | ❌ |
| `/api/trades` | GET | 获取交易记录 | ✅ |
| `/api/positions/current` | GET | 获取当前持仓 | ✅ |
| `/api/trends/latest` | GET | 获取最新趋势 | ✅ |
| `/api/indicators/active` | GET | 获取生效指标 | ✅ |
| `/api/history` | GET | 获取历史记录 | ✅ |
| `/api/ai/chat` | POST | AI 对话 | ✅ |
| `/ws/realtime` | WS | 实时数据推送 | ✅ |

---

## 2. 认证接口

### 2.1 用户登录

**端点**: `POST /api/auth/login`

**请求体**:
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**错误响应**:
```json
{
  "detail": "Invalid credentials"
}
```

---

## 3. 交易数据接口

### 3.1 获取交易记录

**端点**: `GET /api/trades`

**查询参数**:
- `limit` (int, 可选): 返回数量，默认 50
- `offset` (int, 可选): 偏移量，默认 0
- `strategy` (string, 可选): 策略筛选
- `start_date` (string, 可选): 开始日期 (YYYY-MM-DD)
- `end_date` (string, 可选): 结束日期 (YYYY-MM-DD)

**请求示例**:
```bash
GET /api/trades?limit=20&strategy=momentum
Authorization: Bearer <token>
```

**响应**:
```json
{
  "total": 150,
  "limit": 20,
  "offset": 0,
  "data": [
    {
      "id": 1,
      "order_id": "12345",
      "symbol": "BTCUSDT",
      "side": "long",
      "action": "open",
      "amount": 0.001,
      "price": 50000.0,
      "pnl": 0.0,
      "pnl_percent": 0.0,
      "strategy": "momentum",
      "reason": "强势突破",
      "status": "filled",
      "created_at": "2026-01-09T10:30:00Z"
    }
  ]
}
```

---

### 3.2 获取当前持仓

**端点**: `GET /api/positions/current`

**响应**:
```json
{
  "has_position": true,
  "position": {
    "side": "long",
    "amount": 0.001,
    "entry_price": 50000.0,
    "current_price": 51000.0,
    "unrealized_pnl": 1.0,
    "unrealized_pnl_pct": 2.0,
    "stop_loss": 49000.0,
    "take_profit": 52000.0,
    "hold_time_minutes": 120
  },
  "account": {
    "balance": 1000.0,
    "equity": 1001.0,
    "margin_used": 50.0,
    "margin_available": 950.0
  }
}
```

---

## 4. 趋势与指标接口

### 4.1 获取最新趋势

**端点**: `GET /api/trends/latest`

**响应**:
```json
{
  "market_regime": "trending_up",
  "confidence": 0.85,
  "volatility_regime": "normal",
  "price": 51000.0,
  "volatility": 0.02,
  "atr": 500.0,
  "volume_ratio": 1.2,
  "timestamp": "2026-01-09T10:35:00Z"
}
```

---

### 4.2 获取生效指标

**端点**: `GET /api/indicators/active`

**响应**:
```json
{
  "indicators": [
    {
      "name": "RSI",
      "value": 65.5,
      "signal": "neutral",
      "threshold": {
        "overbought": 70,
        "oversold": 30
      }
    },
    {
      "name": "MACD",
      "value": 150.0,
      "signal": "bullish",
      "histogram": 50.0
    },
    {
      "name": "EMA_20",
      "value": 50500.0,
      "signal": "above"
    }
  ],
  "timestamp": "2026-01-09T10:35:00Z"
}
```

---

## 5. 历史记录接口

### 5.1 获取历史记录

**端点**: `GET /api/history`

**查询参数**:
- `type` (string): 记录类型 (trades/signals/decisions)
- `limit` (int): 返回数量
- `offset` (int): 偏移量
- `start_date` (string): 开始日期
- `end_date` (string): 结束日期

**响应**:
```json
{
  "type": "trades",
  "total": 500,
  "data": [
    {
      "trade_id": "t_001",
      "timestamp": "2026-01-09T08:00:00Z",
      "strategy": "momentum",
      "signal": "buy",
      "entry_price": 50000.0,
      "exit_price": 51000.0,
      "pnl": 1.0,
      "pnl_pct": 2.0,
      "hold_time_minutes": 60
    }
  ]
}
```

---

## 6. AI 交互接口

### 6.1 AI 对话

**端点**: `POST /api/ai/chat`

**请求体**:
```json
{
  "message": "分析当前市场趋势",
  "context": {
    "include_position": true,
    "include_recent_trades": true
  }
}
```

**响应**:
```json
{
  "response": "当前市场处于上升趋势，RSI 为 65.5，接近超买区域...",
  "confidence": 0.8,
  "suggestions": [
    "考虑部分止盈",
    "关注回调支撑位 50500"
  ],
  "timestamp": "2026-01-09T10:40:00Z"
}
```

---

## 7. WebSocket 实时推送

### 7.1 连接建立

**端点**: `WS /ws/realtime`

**连接参数**:
```
ws://localhost:8000/ws/realtime?token=<jwt_token>
```

### 7.2 消息格式

**订阅消息**:
```json
{
  "action": "subscribe",
  "channels": ["trades", "positions", "trends"]
}
```

**推送消息 - 新交易**:
```json
{
  "type": "trade",
  "data": {
    "id": 151,
    "action": "open",
    "price": 51000.0,
    "timestamp": "2026-01-09T10:45:00Z"
  }
}
```

**推送消息 - 持仓更新**:
```json
{
  "type": "position",
  "data": {
    "unrealized_pnl": 1.5,
    "unrealized_pnl_pct": 3.0,
    "current_price": 51500.0
  }
}
```

**心跳消息**:
```json
{
  "type": "ping",
  "timestamp": "2026-01-09T10:45:30Z"
}
```

---

## 8. 错误处理

### 8.1 错误响应格式

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Token has expired",
    "details": {
      "expired_at": "2026-01-08T10:00:00Z"
    }
  }
}
```

### 8.2 错误码列表

| 错误码 | HTTP 状态 | 说明 |
|--------|----------|------|
| `INVALID_CREDENTIALS` | 401 | 用户名或密码错误 |
| `INVALID_TOKEN` | 401 | Token 无效或过期 |
| `FORBIDDEN` | 403 | 无权限访问 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `RATE_LIMIT` | 429 | 请求过于频繁 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |

---

## 9. FastAPI 实现示例

### 9.1 项目结构

```
apps/api/
├── main.py              # 应用入口
├── config.py            # 配置
├── auth.py              # 认证模块
├── websocket.py         # WebSocket 处理
├── models/              # 数据模型
│   ├── trade.py
│   ├── position.py
│   └── trend.py
├── routes/              # API 路由
│   ├── auth.py
│   ├── trades.py
│   ├── positions.py
│   ├── trends.py
│   ├── indicators.py
│   ├── history.py
│   └── ai.py
├── services/            # 业务逻辑
│   ├── trade_service.py
│   ├── position_service.py
│   └── ai_service.py
└── requirements.txt
```

### 9.2 核心代码示例

**main.py**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import trades, positions, trends, auth
from websocket import websocket_endpoint

app = FastAPI(title="Trading Dashboard API")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-dashboard.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])

# WebSocket
app.add_websocket_route("/ws/realtime", websocket_endpoint)
```

**routes/trades.py**:
```python
from fastapi import APIRouter, Depends, Query
from typing import Optional
from auth import get_current_user
from services.trade_service import TradeService

router = APIRouter()

@router.get("")
async def get_trades(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    strategy: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    service = TradeService()
    return await service.get_trades(limit, offset, strategy)
```

---

**下一步**: 阅读 `04-前端Dashboard设计.md` 了解前端组件设计。
