"""
Backtest History API routes
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from backtest.summary_repository import SummaryRepository
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtests", tags=["backtest-history"])


class SessionSummary(BaseModel):
    """Session summary response model"""
    session_id: str
    created_at: int
    updated_at: int
    status: str
    symbol: str
    timeframe: str
    start_ts: int
    end_ts: int
    strategy_name: str
    strategy_params: Optional[str] = None
    total_trades: Optional[int] = None
    win_rate: Optional[float] = None
    total_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe: Optional[float] = None


class SessionListResponse(BaseModel):
    """Session list response with pagination"""
    data: List[SessionSummary]
    next_cursor: Optional[str] = None
    has_more: bool


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    cursor: Optional[str] = Query(None, description="Pagination cursor (created_at:session_id)"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_dir: str = Query("desc", regex="^(asc|desc)$", description="Sort direction"),
    # Filters
    strategy_name: Optional[str] = Query(None, description="Filter by strategy name"),
    created_at_from: Optional[int] = Query(None, description="Filter by created_at >= timestamp"),
    created_at_to: Optional[int] = Query(None, description="Filter by created_at <= timestamp"),
    total_return_min: Optional[float] = Query(None, description="Filter by total_return >= value"),
    total_return_max: Optional[float] = Query(None, description="Filter by total_return <= value"),
    sharpe_min: Optional[float] = Query(None, description="Filter by sharpe >= value"),
    sharpe_max: Optional[float] = Query(None, description="Filter by sharpe <= value"),
    max_drawdown_min: Optional[float] = Query(None, description="Filter by max_drawdown >= value"),
    max_drawdown_max: Optional[float] = Query(None, description="Filter by max_drawdown <= value"),
    win_rate_min: Optional[float] = Query(None, description="Filter by win_rate >= value"),
    win_rate_max: Optional[float] = Query(None, description="Filter by win_rate <= value"),
):
    """
    List backtest sessions with pagination and filters

    Supports:
    - Cursor-based pagination for stable results
    - Multi-field filtering (strategy, time range, performance metrics)
    - Sorting by any metric field
    """
    try:
        repo = SummaryRepository()

        # Build filters dict
        filters = {}
        if strategy_name:
            filters["strategy_name"] = strategy_name
        if created_at_from is not None:
            filters["created_at_from"] = created_at_from
        if created_at_to is not None:
            filters["created_at_to"] = created_at_to
        if total_return_min is not None:
            filters["total_return_min"] = total_return_min
        if total_return_max is not None:
            filters["total_return_max"] = total_return_max
        if sharpe_min is not None:
            filters["sharpe_min"] = sharpe_min
        if sharpe_max is not None:
            filters["sharpe_max"] = sharpe_max
        if max_drawdown_min is not None:
            filters["max_drawdown_min"] = max_drawdown_min
        if max_drawdown_max is not None:
            filters["max_drawdown_max"] = max_drawdown_max
        if win_rate_min is not None:
            filters["win_rate_min"] = win_rate_min
        if win_rate_max is not None:
            filters["win_rate_max"] = win_rate_max

        # Query summaries
        summaries, next_cursor = repo.list_summaries(
            cursor=cursor,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters if filters else None
        )

        return SessionListResponse(
            data=[SessionSummary(**s) for s in summaries],
            next_cursor=next_cursor,
            has_more=next_cursor is not None
        )
    except ValueError as e:
        # Invalid input parameters (e.g., invalid sort_by)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the full error but don't expose internal details
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/{session_id}/summary", response_model=SessionSummary)
async def get_session_summary(session_id: str):
    """Get session summary by ID"""
    try:
        repo = SummaryRepository()
        summary = repo.get_summary(session_id)

        if not summary:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionSummary(**summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get session summary: {session_id}")
        raise HTTPException(status_code=500, detail="Internal server error")
