"""
Trading Dashboard API - 主入口文件
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import ai as ai_routes
from apps.api.routes import auth as auth_routes
from apps.api.routes import history as history_routes
from apps.api.routes import indicators as indicators_routes
from apps.api.routes import positions as positions_routes
from apps.api.routes import statistics as statistics_routes
from apps.api.routes import trades as trades_routes
from apps.api.routes import trends as trends_routes
from apps.api.websocket import router as websocket_router

# 加载环境变量
load_dotenv()

# 创建 FastAPI 应用
app = FastAPI(
    title="Trading Dashboard API",
    version="1.0.0",
    description="API for trading data visualization",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_routes.router)
app.include_router(trades_routes.router)
app.include_router(positions_routes.router)
app.include_router(trends_routes.router)
app.include_router(indicators_routes.router)
app.include_router(history_routes.router)
app.include_router(statistics_routes.router)
app.include_router(ai_routes.router)
app.include_router(websocket_router)

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Trading Dashboard API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
