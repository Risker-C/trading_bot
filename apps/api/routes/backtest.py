"""
Backtest API routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from apps.api.models.backtest import (
    CreateSessionRequest,
    SessionResponse,
    SessionDetailResponse
)
from backtest.repository import BacktestRepository
from backtest.engine import BacktestEngine
from backtest.data_provider import HistoricalDataProvider
from strategies.strategies import get_strategy

router = APIRouter(prefix="/api/backtests", tags=["backtest"])
repo = BacktestRepository()
engine = BacktestEngine(repo)
data_provider = HistoricalDataProvider()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create new backtest session"""
    try:
        session_id = repo.create_session(request.dict())
        return SessionResponse(
            session_id=session_id,
            status="created",
            created_at=int(__import__('datetime').datetime.utcnow().timestamp())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_backtest_task(session_id: str, params: dict):
    """Background task to run backtest"""
    try:
        klines = data_provider.fetch_klines(
            params['symbol'],
            params['timeframe'],
            params['start_ts'],
            params['end_ts']
        )

        if klines.empty:
            repo.update_session_status(session_id, "failed", "No kline data available")
            return

        strategy = get_strategy(params['strategy_name'], klines)
        engine.run(session_id, klines, strategy.analyze, params['initial_capital'])
    except Exception as e:
        repo.update_session_status(session_id, "failed", str(e))


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, background_tasks: BackgroundTasks):
    """Start backtest execution"""
    try:
        conn = repo._get_conn()
        cursor = conn.execute("SELECT * FROM backtest_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        params = {
            'symbol': row[4],
            'timeframe': row[5],
            'start_ts': row[6],
            'end_ts': row[7],
            'initial_capital': row[8],
            'strategy_name': row[12]
        }

        background_tasks.add_task(run_backtest_task, session_id, params)
        return {"status": "running", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop backtest execution"""
    try:
        repo.update_session_status(session_id, "stopped")
        return {"status": "stopped", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/metrics")
async def get_metrics(session_id: str):
    """Get backtest metrics"""
    try:
        conn = repo._get_conn()
        cursor = conn.execute("SELECT * FROM backtest_metrics WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "total_trades": row[1],
            "win_rate": row[2],
            "total_pnl": row[3],
            "total_return": row[4],
            "max_drawdown": row[5],
            "sharpe": row[6],
            "profit_factor": row[7],
            "expectancy": row[8],
            "avg_win": row[9],
            "avg_loss": row[10]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/trades")
async def get_trades(session_id: str, limit: int = 100):
    """Get backtest trades"""
    try:
        conn = repo._get_conn()
        cursor = conn.execute(
            "SELECT * FROM backtest_trades WHERE session_id = ? ORDER BY ts DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()

        trades = []
        for row in rows:
            trades.append({
                "id": row[0],
                "ts": row[2],
                "symbol": row[3],
                "side": row[4],
                "action": row[5],
                "qty": row[6],
                "price": row[7],
                "fee": row[8],
                "pnl": row[10],
                "pnl_pct": row[11],
                "strategy_name": row[12],
                "reason": row[13]
            })

        return trades
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
