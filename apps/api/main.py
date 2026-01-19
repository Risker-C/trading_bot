"""
Trading Dashboard API - 主入口文件
"""
import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import ai as ai_routes
from apps.api.routes import auth as auth_routes
from apps.api.routes import backtest as backtest_routes
from apps.api.routes import backtest_history as backtest_history_routes
from apps.api.routes import backtest_ai as backtest_ai_routes
from apps.api.routes import change_requests as change_requests_routes
from apps.api.routes import decisions as decisions_routes
from apps.api.routes import history as history_routes
from apps.api.routes import indicators as indicators_routes
from apps.api.routes import optimization as optimization_routes
from apps.api.routes import positions as positions_routes
from apps.api.routes import statistics as statistics_routes
from apps.api.routes import stream as stream_routes
from apps.api.routes import trades as trades_routes
from apps.api.routes import trends as trends_routes
from apps.api.services.ticker_service import ticker_service

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
app.include_router(backtest_routes.router)
app.include_router(backtest_history_routes.router)
app.include_router(backtest_ai_routes.router)
app.include_router(change_requests_routes.router)
app.include_router(optimization_routes.router)
app.include_router(trades_routes.router)
app.include_router(positions_routes.router)
app.include_router(trends_routes.router)
app.include_router(indicators_routes.router)
app.include_router(history_routes.router)
app.include_router(statistics_routes.router)
app.include_router(ai_routes.router)
app.include_router(decisions_routes.router)
app.include_router(stream_routes.router)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化服务"""
    try:
        # 初始化 ticker 服务
        await ticker_service.initialize()

        # 启动后台刷新任务
        asyncio.create_task(ticker_service.start_background_refresh())
    except Exception as e:
        print(f"启动 ticker 服务失败: {e}")


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
