import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from claude_analyzer import ClaudeAnalyzer
from utils.logger_utils import get_logger

from apps.api.services.indicator_service import IndicatorService
from apps.api.services.trade_service import TradeService
from apps.api.services.trend_service import TrendService


class AIService:
    """Lightweight wrapper around ClaudeAnalyzer for dashboard chat."""

    def __init__(
        self,
        analyzer: Optional[ClaudeAnalyzer] = None,
        trade_service: Optional[TradeService] = None,
        trend_service: Optional[TrendService] = None,
        indicator_service: Optional[IndicatorService] = None,
    ):
        self.analyzer = analyzer or ClaudeAnalyzer()
        self.trade_service = trade_service or TradeService()
        self.trend_service = trend_service or TrendService(trade_service=self.trade_service)
        self.indicator_service = indicator_service or IndicatorService(trade_service=self.trade_service)
        self.logger = get_logger(__name__)

    async def chat(self, message: str, market_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.analyzer.enabled or not getattr(self.analyzer, "client", None):
            raise RuntimeError("Claude analyzer is disabled")

        context = await self._build_context(market_context)
        prompt = self._build_prompt(message, context)
        reply = await asyncio.to_thread(self._invoke_claude, prompt)

        return {
            "reply": reply,
            "context": context,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _build_context(self, runtime_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        summary_task = asyncio.create_task(self.trade_service.get_summary())
        trend_task = asyncio.create_task(self.trend_service.latest_trend())
        indicators_task = asyncio.create_task(self.indicator_service.get_active_indicators())

        summary = await summary_task
        trend = await trend_task
        indicators = await indicators_task

        context: Dict[str, Any] = {
            "summary": summary.model_dump(),
            "trend": trend.model_dump(),
            "indicators": [indicator.model_dump() for indicator in indicators],
        }
        if runtime_context:
            context["extra_context"] = runtime_context
        return context

    @staticmethod
    def _build_prompt(message: str, context: Dict[str, Any]) -> str:
        serialized_context = json.dumps(context, ensure_ascii=False, indent=2)
        return (
            "你是一名资深量化交易分析师，请基于以下上下文提供建议：\n\n"
            f"{serialized_context}\n\n"
            f"用户问题: {message}\n"
            "请用中文输出结论，包含明确的风险提示。"
        )

    def _invoke_claude(self, prompt: str) -> str:
        response = self.analyzer.client.messages.create(
            model=self.analyzer.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
