"""
Backtest API routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from apps.api.models.backtest import (
    CreateSessionRequest,
    SessionResponse,
    SessionDetailResponse
)
from backtest.repository import BacktestRepository
from backtest.engine import BacktestEngine
from backtest.data_provider import HistoricalDataProvider
from strategies.strategies import get_strategy
import csv
from io import StringIO

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
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"[Backtest {session_id[:8]}] 开始执行回测任务")
        logger.info(f"[Backtest {session_id[:8]}] 参数: {params}")

        logger.info(f"[Backtest {session_id[:8]}] 开始获取历史K线数据...")
        klines = data_provider.fetch_klines(
            params['symbol'],
            params['timeframe'],
            params['start_ts'],
            params['end_ts']
        )
        logger.info(f"[Backtest {session_id[:8]}] 获取到 {len(klines)} 条K线数据")

        if klines.empty:
            logger.warning(f"[Backtest {session_id[:8]}] K线数据为空，回测失败")
            repo.update_session_status(session_id, "failed", "No kline data available")
            return

        logger.info(f"[Backtest {session_id[:8]}] 加载策略: {params['strategy_name']}")

        logger.info(f"[Backtest {session_id[:8]}] 开始运行回测引擎...")
        engine.run(session_id, klines, params['strategy_name'], params['initial_capital'])
        logger.info(f"[Backtest {session_id[:8]}] 回测完成")
    except Exception as e:
        logger.error(f"[Backtest {session_id[:8]}] 回测失败: {str(e)}", exc_info=True)
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


@router.get("/sessions/{session_id}/klines")
async def get_klines(session_id: str, limit: int = 1000):
    """Get backtest klines for chart"""
    try:
        conn = repo._get_conn()
        cursor = conn.execute(
            "SELECT ts, open, high, low, close, volume FROM backtest_klines WHERE session_id = ? ORDER BY ts ASC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()

        klines = []
        for row in rows:
            klines.append({
                "timestamp": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5]
            })

        return klines
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/export")
async def export_report(session_id: str):
    """Export backtest report as CSV"""
    try:
        conn = repo._get_conn()

        # Get session info
        session_cursor = conn.execute("SELECT * FROM backtest_sessions WHERE id = ?", (session_id,))
        session = session_cursor.fetchone()

        # Get metrics
        metrics_cursor = conn.execute("SELECT * FROM backtest_metrics WHERE session_id = ?", (session_id,))
        metrics = metrics_cursor.fetchone()

        # Get trades
        trades_cursor = conn.execute("SELECT * FROM backtest_trades WHERE session_id = ? ORDER BY ts", (session_id,))
        trades = trades_cursor.fetchall()

        conn.close()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Generate CSV
        output = StringIO()
        writer = csv.writer(output)

        # Session info
        writer.writerow(["Session Info"])
        writer.writerow(["Symbol", session[4]])
        writer.writerow(["Timeframe", session[5]])
        writer.writerow(["Initial Capital", session[8]])
        writer.writerow(["Strategy", session[12]])
        writer.writerow([])

        # Metrics
        if metrics:
            writer.writerow(["Metrics"])
            writer.writerow(["Total Trades", metrics[1]])
            writer.writerow(["Win Rate", f"{metrics[2]*100:.2f}%"])
            writer.writerow(["Total PnL", f"{metrics[3]:.2f}"])
            writer.writerow(["Total Return", f"{metrics[4]:.2f}%"])
            writer.writerow(["Max Drawdown", f"{metrics[5]:.2f}%"])
            writer.writerow(["Sharpe Ratio", f"{metrics[6]:.2f}"])
            writer.writerow([])

        # Trades
        writer.writerow(["Trades"])
        writer.writerow(["Timestamp", "Symbol", "Side", "Action", "Quantity", "Price", "Fee", "PnL", "PnL %", "Strategy", "Reason"])
        for trade in trades:
            writer.writerow([trade[2], trade[3], trade[4], trade[5], trade[6], trade[7], trade[8], trade[10] or "", trade[11] or "", trade[12], trade[13]])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=backtest_{session_id}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
