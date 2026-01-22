"""
Backtest AI Analysis API routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from backtest.ai_service import BacktestAIService
from backtest.repository_factory import get_ai_report_repository
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtests", tags=["backtest-ai"])


class AIAnalysisRequest(BaseModel):
    """Request to trigger AI analysis"""
    pass


class AIAnalysisResponse(BaseModel):
    """AI analysis response"""
    report_id: Optional[str] = None
    summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    param_suggestions: dict


class CompareRequest(BaseModel):
    """Request to compare multiple sessions"""
    session_ids: List[str]


class CompareResponse(BaseModel):
    """Comparison response"""
    compare_group_id: str
    summary: str
    best_session_id: str
    comparison: List[dict]
    recommendations: List[str]


@router.post("/sessions/{session_id}/ai-analysis", response_model=AIAnalysisResponse)
async def analyze_session(session_id: str, background_tasks: BackgroundTasks):
    """
    Trigger AI analysis for a backtest session

    This endpoint analyzes the backtest results and provides:
    - Overall performance summary
    - Strategy strengths and weaknesses
    - Optimization recommendations
    - Parameter adjustment suggestions
    """
    try:
        service = BacktestAIService()

        # Run analysis (could be moved to background for long-running tasks)
        result = service.analyze_session(session_id)

        # Get the saved report ID
        report = service.ai_repo.get_latest_report(session_id)
        report_id = report["id"] if report else None

        return AIAnalysisResponse(
            report_id=report_id,
            summary=result.get("summary", ""),
            strengths=result.get("strengths", []),
            weaknesses=result.get("weaknesses", []),
            recommendations=result.get("recommendations", []),
            param_suggestions=result.get("param_suggestions", {})
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to analyze session {session_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/{session_id}/ai-analysis", response_model=AIAnalysisResponse)
async def get_session_analysis(session_id: str):
    """
    Get the latest AI analysis for a session

    Returns the most recent analysis report if available
    """
    try:
        repo = get_ai_report_repository()
        report = repo.get_latest_report(session_id)

        if not report:
            raise HTTPException(status_code=404, detail="No analysis found for this session")

        return AIAnalysisResponse(
            report_id=report["id"],
            summary=report["summary"],
            strengths=report["strengths"],
            weaknesses=report["weaknesses"],
            recommendations=report["recommendations"],
            param_suggestions=report["param_suggestions"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get analysis for session {session_id}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ai-analysis/compare", response_model=CompareResponse)
async def compare_sessions(request: CompareRequest):
    """
    Compare multiple backtest sessions

    Analyzes and ranks multiple sessions based on:
    - Risk-adjusted returns
    - Consistency
    - Drawdown management
    - Overall performance

    Provides recommendations for parameter optimization
    """
    try:
        if len(request.session_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 sessions required for comparison"
            )

        if len(request.session_ids) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 sessions allowed for comparison"
            )

        service = BacktestAIService()
        result = service.compare_sessions(request.session_ids)

        return CompareResponse(
            compare_group_id=result.get("compare_group_id", ""),
            summary=result.get("summary", ""),
            best_session_id=result.get("best_session_id", request.session_ids[0]),
            comparison=result.get("comparison", []),
            recommendations=result.get("recommendations", [])
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Failed to compare sessions")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ai-analysis/groups/{compare_group_id}")
async def get_comparison_group(compare_group_id: str):
    """Get all reports in a comparison group"""
    try:
        repo = get_ai_report_repository()
        reports = repo.get_reports_by_group(compare_group_id)

        if not reports:
            raise HTTPException(status_code=404, detail="Comparison group not found")

        return {"reports": reports}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get comparison group {compare_group_id}")
        raise HTTPException(status_code=500, detail="Internal server error")
