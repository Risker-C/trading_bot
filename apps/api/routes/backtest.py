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
from backtest.repository_factory import get_backtest_repository
from backtest.engine import BacktestEngine
from backtest.data_provider import HistoricalDataProvider
import csv
from io import StringIO
import json

router = APIRouter(prefix="/api/backtests", tags=["backtest"])


def _get_repo():
    """创建新的Repository实例 (根据环境变量选择SQLite或Supabase)"""
    return get_backtest_repository()


def _build_backtest_components():
    """创建新的回测组件实例"""
    repo = _get_repo()
    engine = BacktestEngine(repo)
    data_provider = HistoricalDataProvider()
    return repo, engine, data_provider


def _parse_strategy_params(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str) and raw_value:
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return None
    return None


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
        session = repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        strategy_params = _parse_strategy_params(session.get('strategy_params'))

        params = {
            'symbol': session.get('symbol'),
            'timeframe': session.get('timeframe'),
            'start_ts': session.get('start_ts'),
            'end_ts': session.get('end_ts'),
            'initial_capital': session.get('initial_capital'),
            'strategy_name': session.get('strategy_name'),
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
        session = repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        metrics = repo.get_metrics(session_id)
        if metrics:
            total_pnl = metrics.get('total_pnl', 0)
            total_return = metrics.get('total_return', 0)
        else:
            total_pnl = 0
            total_return = 0
        final_capital = None
        if session.get('initial_capital') is not None:
            final_capital = session.get('initial_capital') + total_pnl

        return {
            "id": session.get('id'),
            "created_at": session.get('created_at'),
            "updated_at": session.get('updated_at'),
            "status": session.get('status'),
            "symbol": session.get('symbol'),
            "timeframe": session.get('timeframe'),
            "start_ts": session.get('start_ts'),
            "end_ts": session.get('end_ts'),
            "initial_capital": session.get('initial_capital'),
            "final_capital": final_capital,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "strategy_name": session.get('strategy_name'),
            "strategy_params": session.get('strategy_params'),
            "error_message": session.get('error_message')
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
        metrics = repo.get_metrics(session_id)
        if not metrics:
            return None

        return {
            "total_trades": metrics.get('total_trades'),
            "win_rate": metrics.get('win_rate'),
            "total_pnl": metrics.get('total_pnl'),
            "total_return": metrics.get('total_return'),
            "max_drawdown": metrics.get('max_drawdown'),
            "sharpe": metrics.get('sharpe'),
            "profit_factor": metrics.get('profit_factor'),
            "expectancy": metrics.get('expectancy'),
            "avg_win": metrics.get('avg_win'),
            "avg_loss": metrics.get('avg_loss')
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
        desc = limit is not None
        trades = repo.get_trades(session_id, limit=limit, desc=desc)

        return [
            {
                "id": trade.get('id'),
                "ts": trade.get('ts'),
                "symbol": trade.get('symbol'),
                "side": trade.get('side'),
                "action": trade.get('action'),
                "qty": trade.get('qty'),
                "price": trade.get('price'),
                "fee": trade.get('fee'),
                "pnl": trade.get('pnl'),
                "pnl_pct": trade.get('pnl_pct'),
                "strategy_name": trade.get('strategy_name'),
                "reason": trade.get('reason'),
                "open_trade_id": trade.get('open_trade_id')
            }
            for trade in trades
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/klines")
async def get_klines(session_id: str, limit: int = None, before: int = None):
    """Get backtest klines for chart

    Args:
        session_id: 回测会话ID
        limit: 返回记录数限制（None表示返回所有K线）
        before: 返回此时间戳之前的K线（用于向前加载更多数据）
    """
    try:
        repo = _get_repo()
        if before is not None and limit is None:
            limit = 1000
        klines = repo.get_klines(session_id, limit=limit, before=before)

        return [
            {
                "timestamp": kline.get('ts'),
                "open": kline.get('open'),
                "high": kline.get('high'),
                "low": kline.get('low'),
                "close": kline.get('close'),
                "volume": kline.get('volume')
            }
            for kline in klines
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/export")
async def export_report(session_id: str):
    """Export backtest report as CSV"""
    try:
        repo = _get_repo()
        session = repo.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        metrics = repo.get_metrics(session_id)
        trades = repo.get_trades(session_id, limit=None, desc=False)

        # Generate CSV
        output = StringIO()
        writer = csv.writer(output)

        # Session info
        writer.writerow(["Session Info"])
        writer.writerow(["Symbol", session.get('symbol')])
        writer.writerow(["Timeframe", session.get('timeframe')])
        writer.writerow(["Initial Capital", session.get('initial_capital')])
        writer.writerow(["Strategy", session.get('strategy_name')])
        writer.writerow([])

        # Metrics
        if metrics:
            writer.writerow(["Metrics"])
            writer.writerow(["Total Trades", metrics.get('total_trades')])
            win_rate = metrics.get('win_rate')
            writer.writerow(["Win Rate", f"{(win_rate or 0)*100:.2f}%"])
            total_pnl = metrics.get('total_pnl')
            writer.writerow(["Total PnL", f"{(total_pnl or 0):.2f}"])
            total_return = metrics.get('total_return')
            writer.writerow(["Total Return", f"{(total_return or 0):.2f}%"])
            max_drawdown = metrics.get('max_drawdown')
            writer.writerow(["Max Drawdown", f"{(max_drawdown or 0):.2f}%"])
            sharpe = metrics.get('sharpe')
            writer.writerow(["Sharpe Ratio", f"{(sharpe or 0):.2f}"])
            writer.writerow([])

        # Trades
        writer.writerow(["Trades"])
        writer.writerow(["Timestamp", "Symbol", "Side", "Action", "Quantity", "Price", "Fee", "PnL", "PnL %", "Strategy", "Reason"])
        for trade in trades:
            writer.writerow([
                trade.get('ts'),
                trade.get('symbol'),
                trade.get('side'),
                trade.get('action'),
                trade.get('qty'),
                trade.get('price'),
                trade.get('fee'),
                trade.get('pnl') or "",
                trade.get('pnl_pct') or "",
                trade.get('strategy_name'),
                trade.get('reason')
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=backtest_{session_id}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
