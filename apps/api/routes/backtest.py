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
import csv
from io import StringIO

router = APIRouter(prefix="/api/backtests", tags=["backtest"])


def _get_repo():
    """创建新的Repository实例"""
    return BacktestRepository()


def _build_backtest_components():
    """创建新的回测组件实例"""
    repo = _get_repo()
    engine = BacktestEngine(repo)
    data_provider = HistoricalDataProvider()
    return repo, engine, data_provider


@router.post("/sessions", response_model=SessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create new backtest session"""
    try:
        repo = _get_repo()
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
    import gc
    logger = logging.getLogger(__name__)

    # 初始化变量
    repo = None
    engine = None
    data_provider = None
    klines = None
    kline_batch = None

    try:
        # 创建新的组件实例
        repo, engine, data_provider = _build_backtest_components()

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

        # 保存K线到数据库以便前端展示图表（分批处理）
        kline_batch = []
        for ts, row in klines.iterrows():
            kline_batch.append({
                'ts': int(ts.timestamp()),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            })
            # 每1000条写入一次
            if len(kline_batch) >= 1000:
                repo.save_klines(session_id, kline_batch)
                kline_batch.clear()

        # 写入剩余的K线
        if kline_batch:
            repo.save_klines(session_id, kline_batch)

        # 判断是否为多策略模式
        strategy_params = params.get('strategy_params')
        if strategy_params and strategy_params.get('strategies'):
            logger.info(f"[Backtest {session_id[:8]}] 加载多策略配置: {len(strategy_params['strategies'])} 个策略")
        else:
            logger.info(f"[Backtest {session_id[:8]}] 加载单策略: {params['strategy_name']}")

        logger.info(f"[Backtest {session_id[:8]}] 开始运行回测引擎...")
        engine.run(
            session_id,
            klines,
            params['strategy_name'],
            params['initial_capital'],
            strategy_params=strategy_params
        )
        logger.info(f"[Backtest {session_id[:8]}] 回测完成")
    except Exception as e:
        logger.error(f"[Backtest {session_id[:8]}] 回测失败: {str(e)}", exc_info=True)
        if repo is not None:
            repo.update_session_status(session_id, "failed", str(e))
    finally:
        # 清理资源
        logger.info(f"[Backtest {session_id[:8]}] 开始清理资源...")

        if data_provider is not None:
            try:
                data_provider.close()
            except Exception as close_err:
                logger.warning(f"[Backtest {session_id[:8]}] 关闭数据提供者失败: {close_err}")

        if kline_batch:
            kline_batch.clear()

        if klines is not None:
            del klines

        if engine is not None:
            del engine

        if repo is not None:
            del repo

        # 强制垃圾回收
        gc.collect()
        logger.info(f"[Backtest {session_id[:8]}] 资源清理完成")


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, background_tasks: BackgroundTasks):
    """Start backtest execution"""
    try:
        repo = _get_repo()
        conn = repo._get_conn()
        cursor = conn.execute("SELECT * FROM backtest_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        # 解析 strategy_params（JSON 字段）
        import json
        strategy_params_raw = row[13] if len(row) > 13 and row[13] else None
        strategy_params = json.loads(strategy_params_raw) if strategy_params_raw else None

        params = {
            'symbol': row[4],
            'timeframe': row[5],
            'start_ts': row[6],
            'end_ts': row[7],
            'initial_capital': row[8],
            'strategy_name': row[12],
            'strategy_params': strategy_params
        }

        background_tasks.add_task(run_backtest_task, session_id, params)
        return {"status": "running", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop backtest execution"""
    try:
        repo = _get_repo()
        repo.update_session_status(session_id, "stopped")
        return {"status": "stopped", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get backtest session details"""
    try:
        repo = _get_repo()
        conn = repo._get_conn()
        cursor = conn.execute("SELECT * FROM backtest_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "id": row[0],
            "created_at": row[1],
            "updated_at": row[2],
            "status": row[3],
            "symbol": row[4],
            "timeframe": row[5],
            "start_ts": row[6],
            "end_ts": row[7],
            "initial_capital": row[8],
            "final_capital": row[9],
            "total_pnl": row[10],
            "total_return": row[11],
            "strategy_name": row[12],
            "strategy_params": row[13],
            "error_message": row[14] if len(row) > 14 else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/metrics")
async def get_metrics(session_id: str):
    """Get backtest metrics"""
    try:
        repo = _get_repo()
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
async def get_trades(session_id: str, limit: int = None):
    """Get backtest trades

    Args:
        session_id: 回测会话ID
        limit: 返回记录数限制（None表示返回所有记录）
    """
    try:
        repo = _get_repo()
        conn = repo._get_conn()

        # 如果没有指定limit，返回所有交易记录
        if limit is None:
            cursor = conn.execute(
                "SELECT * FROM backtest_trades WHERE session_id = ? ORDER BY ts ASC",
                (session_id,)
            )
        else:
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
                "reason": row[13],
                "open_trade_id": row[14] if len(row) > 14 else None
            })

        return trades
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/klines")
async def get_klines(session_id: str, limit: int = None):
    """Get backtest klines for chart

    Args:
        session_id: 回测会话ID
        limit: 返回记录数限制（None表示返回所有K线）
    """
    try:
        repo = _get_repo()
        conn = repo._get_conn()

        # 如果没有指定limit，返回所有K线数据
        if limit is None:
            cursor = conn.execute(
                "SELECT ts, open, high, low, close, volume FROM backtest_klines WHERE session_id = ? ORDER BY ts ASC",
                (session_id,)
            )
        else:
            cursor = conn.execute(
                "SELECT ts, open, high, low, close, volume FROM backtest_klines WHERE session_id = ? ORDER BY ts DESC LIMIT ?",
                (session_id, limit)
            )

        rows = cursor.fetchall()
        conn.close()

        klines = []
        # 如果使用了limit，需要反转顺序（因为查询是DESC）
        if limit is not None:
            rows = reversed(rows)

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
        repo = _get_repo()
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
