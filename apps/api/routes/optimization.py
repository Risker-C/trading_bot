"""
优化API端点
"""
import asyncio
import json
import ast
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

from backtest.adapters.storage.sqlite_repo import SQLiteRepository
from backtest.adapters.cache.memory_cache import MemoryCache
from backtest.services.optimization_service import OptimizationService
from backtest.services.strategy_version_service import StrategyVersionService
from backtest.services.backtest_service import BacktestService
from backtest.services.data_service import DataService
from backtest.data_provider import HistoricalDataProvider

router = APIRouter(prefix="/api/optimization", tags=["optimization"])

# 初始化服务
repo = SQLiteRepository()
cache = MemoryCache()
provider = HistoricalDataProvider()
data_service = DataService(repo, cache, provider)
backtest_service = BacktestService(repo, cache)
optimization_service = OptimizationService(repo, backtest_service)
strategy_service = StrategyVersionService(repo)


def _parse_params(params_str: str) -> dict:
    """解析参数字符串，支持 JSON 和历史 repr 格式"""
    if not params_str:
        return {}

    try:
        # 尝试 JSON 解析
        return json.loads(params_str)
    except (json.JSONDecodeError, TypeError):
        # 降级：尝试 ast.literal_eval（仅用于历史数据兼容，比 eval 安全）
        try:
            return ast.literal_eval(params_str)
        except:
            return {}


class CreateOptimizationRequest(BaseModel):
    """创建优化任务请求"""
    strategy_name: str
    strategy_version: str
    symbol: str
    timeframe: str
    start_ts: int
    end_ts: int
    algorithm: str  # grid | ga
    search_space: Dict[str, Any]
    target_metric: str = 'sharpe'


class OptimizationResponse(BaseModel):
    """优化任务响应"""
    job_id: str
    status: str


@router.post("/jobs", response_model=OptimizationResponse)
async def create_optimization_job(request: CreateOptimizationRequest):
    """创建优化任务"""

    # 1. 创建或获取策略版本
    strategy_version_id = await strategy_service.create_strategy_version(
        name=request.strategy_name,
        version=request.strategy_version,
        params_schema=request.search_space
    )

    # 2. 获取或拉取K线数据集
    kline_dataset_id, _ = await data_service.get_or_fetch_klines(
        symbol=request.symbol,
        timeframe=request.timeframe,
        start_ts=request.start_ts,
        end_ts=request.end_ts
    )

    # 3. 创建优化任务
    job_id = await optimization_service.create_optimization_job(
        strategy_version_id=strategy_version_id,
        kline_dataset_id=kline_dataset_id,
        algorithm=request.algorithm,
        search_space=request.search_space,
        target_metric=request.target_metric
    )

    return OptimizationResponse(job_id=job_id, status='created')


@router.get("/jobs/{job_id}")
async def get_optimization_job(job_id: str):
    """获取优化任务状态"""

    conn = repo._get_conn()
    try:
        cursor = conn.execute("""
            SELECT id, status, algorithm, created_at
            FROM optimization_jobs WHERE id = ?
        """, (job_id,))

        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="优化任务不存在")

        return {
            'job_id': row[0],
            'status': row[1],
            'algorithm': row[2],
            'created_at': row[3]
        }
    finally:
        conn.close()


@router.get("/jobs/{job_id}/results")
async def get_optimization_results(job_id: str, limit: int = 50):
    """获取优化结果（Top N）"""

    conn = repo._get_conn()
    try:
        cursor = conn.execute("""
            SELECT r.rank, r.score, p.params, r.run_id, r.param_set_id
            FROM optimization_results r
            JOIN parameter_sets p ON r.param_set_id = p.id
            WHERE r.job_id = ?
            ORDER BY r.rank
            LIMIT ?
        """, (job_id, limit))

        rows = cursor.fetchall()

        return {
            'job_id': job_id,
            'results': [
                {
                    'rank': row[0],
                    'score': row[1],
                    'params': _parse_params(row[2]),
                    'run_id': row[3],
                    'param_set_id': row[4]
                }
                for row in rows
            ]
        }
    finally:
        conn.close()


@router.post("/jobs/{job_id}/start")
async def start_optimization_job(job_id: str):
    """启动优化任务（后台执行）"""

    # 使用数据库锁防止并发启动
    conn = repo._get_conn()
    try:
        # 原子性检查并更新状态
        cursor = conn.execute("""
            UPDATE optimization_jobs
            SET status = 'running'
            WHERE id = ? AND status IN ('created', 'failed')
        """, (job_id,))

        if cursor.rowcount == 0:
            # 检查任务是否存在
            cursor = conn.execute("SELECT status FROM optimization_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="优化任务不存在")

            # 任务已在运行或已完成
            raise HTTPException(status_code=400, detail=f"任务状态为 {row[0]}，无法启动")

        conn.commit()
    finally:
        conn.close()

    # 启动后台任务
    asyncio.create_task(optimization_service.run_optimization(job_id))

    return {'job_id': job_id, 'status': 'started'}


@router.get("/strategies")
async def list_strategies():
    """列出所有策略版本"""

    versions = await strategy_service.list_strategy_versions()
    return {'strategies': versions}
