import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import settings as config
from core.trader import BitgetTrader
from risk.execution_filter import get_execution_filter
from strategies.indicators import IndicatorCalculator
from strategies.strategies import Signal, analyze_all_strategies, get_consensus_signal
from utils.logger_utils import get_logger

logger = get_logger("decision_service")


class DecisionStatusService:
    def __init__(self) -> None:
        self._trader: Optional[BitgetTrader] = None
        self._lock = asyncio.Lock()

    async def _get_trader(self) -> BitgetTrader:
        async with self._lock:
            if self._trader is None:
                self._trader = await asyncio.to_thread(BitgetTrader)
        return self._trader

    async def get_status(self) -> Dict[str, Any]:
        status = self._build_base_status()

        try:
            trader = await self._get_trader()
        except Exception as exc:
            logger.error(f"Decision status trader init failed: {exc}")
            status["risk_status"]["reason"] = "trader_unavailable"
            status["blocking_reasons"].append("trader_unavailable")
            return self._finalize_status(status)

        can_trade, risk_reason = trader.risk_manager.can_open_position()
        cooldown_status = trader.risk_manager.get_cooldown_status()
        status["risk_status"] = {
            "can_trade": can_trade,
            "reason": risk_reason or "ok",
            "cooldown_remaining": int(cooldown_status.get("cooldown_remaining", 0)),
        }
        if not can_trade and risk_reason:
            status["blocking_reasons"].append(risk_reason)

        drawdown_allowed, drawdown_reason = trader.drawdown_controller.can_trade()
        status["drawdown_status"] = {
            "allowed": drawdown_allowed,
            "current_drawdown_pct": round(trader.risk_manager.metrics.current_drawdown * 100, 2),
        }
        if not drawdown_allowed and drawdown_reason:
            status["blocking_reasons"].append(drawdown_reason)

        df = await asyncio.to_thread(trader.fetch_ohlcv)
        ticker = await asyncio.to_thread(trader.get_ticker)

        if df is None or df.empty:
            status["blocking_reasons"].append("ohlcv_unavailable")
        if not ticker:
            status["blocking_reasons"].append("ticker_unavailable")

        market_state = {"state": "unknown", "adx": 0.0}
        indicators: Dict[str, Any] = {}
        if df is not None and not df.empty:
            indicators = self._build_indicators(df)
            market_state = indicators.pop("market_state", market_state)
            status["market_state"] = market_state.get("state", "unknown")
            status["market_adx"] = round(float(market_state.get("adx", 0.0)), 2)

        signal = None
        if df is not None and not df.empty:
            if getattr(config, "MULTI_TIMEFRAME_ENABLED", False):
                await asyncio.to_thread(trader.fetch_multi_timeframe_data)
            signal = self._build_signal(df, market_state)

        if signal:
            status["signal_strength"] = round(signal.strength, 4)
            status["signal_confidence"] = round(signal.confidence, 4)
            status["signal_type"] = signal.signal.value
        elif df is not None and not df.empty:
            status["blocking_reasons"].append("no_signal")

        exec_filter = get_execution_filter()
        exec_pass = False
        exec_reason = "execution_filter_skipped"
        exec_details: Dict[str, Any] = {}

        if df is not None and not df.empty and ticker:
            exec_pass, exec_reason, exec_details = exec_filter.check_all(
                df,
                ticker.get("last", 0.0),
                ticker,
                indicators,
                record_rejection=False,
            )

        status["execution_filters"] = self._build_execution_filters(exec_filter, exec_details)
        if not exec_pass and exec_reason:
            status["blocking_reasons"].append(exec_reason)

        status["order_suggestion"] = self._suggest_order(
            signal=signal,
            can_trade=can_trade,
            drawdown_allowed=drawdown_allowed,
            exec_pass=exec_pass,
        )

        status["logic_chain"] = self._build_logic_chain(
            market_state=market_state,
            signal=signal,
            risk_reason=risk_reason,
            can_trade=can_trade,
            drawdown_reason=drawdown_reason,
            drawdown_allowed=drawdown_allowed,
            exec_reason=exec_reason,
            exec_pass=exec_pass,
        )

        return self._finalize_status(status)

    def _build_base_status(self) -> Dict[str, Any]:
        return {
            "signal_strength": 0.0,
            "signal_confidence": 0.0,
            "signal_type": "hold",
            "market_state": "unknown",
            "market_adx": 0.0,
            "risk_status": {
                "can_trade": False,
                "reason": "unknown",
                "cooldown_remaining": 0,
            },
            "drawdown_status": {
                "allowed": True,
                "current_drawdown_pct": 0.0,
            },
            "execution_filters": {},
            "blocking_reasons": [],
            "order_suggestion": "hold",
            "logic_chain": [],
            "updated_at": "",
        }

    def _finalize_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        status["updated_at"] = datetime.utcnow().isoformat()
        deduped = list(dict.fromkeys(status.get("blocking_reasons", [])))
        status["blocking_reasons"] = deduped
        return status

    def _build_indicators(self, df) -> Dict[str, Any]:
        ind = IndicatorCalculator(df)
        volume_ratio = self._latest_value(ind.volume_ratio(), 1.0)
        atr = self._latest_value(ind.atr(), 0.0)
        adx_bundle = ind.adx()
        adx = self._latest_value(adx_bundle.get("adx") if adx_bundle else None, 0.0)
        market_state = ind.market_state()

        return {
            "volume_ratio": volume_ratio,
            "atr": atr,
            "adx": adx,
            "market_state": market_state,
        }

    def _build_signal(self, df, market_state: Dict[str, Any]) -> Optional[Any]:
        if df is None or len(df) < 50:
            return None

        strategies = self._select_strategies(market_state)
        if not strategies:
            return None

        if getattr(config, "USE_CONSENSUS_SIGNAL", False) and len(strategies) > 1:
            return get_consensus_signal(
                df,
                strategies,
                min_agreement=config.MIN_STRATEGY_AGREEMENT,
            )

        signals = analyze_all_strategies(
            df,
            strategies,
            min_strength=config.MIN_SIGNAL_STRENGTH,
            min_confidence=config.MIN_SIGNAL_CONFIDENCE,
        )
        return signals[0] if signals else None

    def _select_strategies(self, market_state: Dict[str, Any]) -> List[str]:
        strategies = list(getattr(config, "ENABLE_STRATEGIES", []))
        state = market_state.get("state")

        if "grid" in strategies and state == "ranging":
            return ["grid"]

        if state in ["trending_up", "trending_down"]:
            trend_strategies = [s for s in strategies if s in ["macd_cross", "ema_cross", "adx_trend"]]
            if trend_strategies:
                return trend_strategies

        return strategies

    def _build_execution_filters(self, exec_filter, details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "spread_ok": details.get("spread_check"),
            "spread_value": details.get("spread_pct"),
            "spread_threshold": exec_filter.max_spread_pct,
            "slippage_ok": details.get("slippage_check"),
            "volatility_ok": details.get("volatility_check"),
            "volume_ratio": details.get("volume_ratio"),
            "price_stability_ok": details.get("price_stability_check"),
            "price_volatility_pct": details.get("price_volatility_pct"),
            "last_rejection_details": exec_filter.last_rejection_details,
            "recent_rejections": exec_filter.get_rejection_history(),
        }

    def _suggest_order(
        self,
        signal: Optional[Any],
        can_trade: bool,
        drawdown_allowed: bool,
        exec_pass: bool,
    ) -> str:
        if not signal or signal.signal not in [Signal.LONG, Signal.SHORT]:
            return "hold"
        if not can_trade or not drawdown_allowed or not exec_pass:
            return "hold"
        return signal.signal.value

    def _build_logic_chain(
        self,
        market_state: Dict[str, Any],
        signal: Optional[Any],
        risk_reason: str,
        can_trade: bool,
        drawdown_reason: str,
        drawdown_allowed: bool,
        exec_reason: str,
        exec_pass: bool,
    ) -> List[Dict[str, Any]]:
        chain = []

        state_label = f"{market_state.get('state', 'unknown')} (ADX {market_state.get('adx', 0.0):.1f})"
        chain.append({"step": "market_state", "result": state_label, "passed": True})

        if signal:
            signal_result = f"{signal.signal.value} {signal.strength:.2f}/{signal.confidence:.2f}"
            signal_passed = signal.signal in [Signal.LONG, Signal.SHORT]
        else:
            signal_result = "no_signal"
            signal_passed = False
        chain.append({"step": "signal", "result": signal_result, "passed": signal_passed})

        chain.append({"step": "risk", "result": risk_reason or "ok", "passed": can_trade})
        chain.append({"step": "drawdown", "result": drawdown_reason or "ok", "passed": drawdown_allowed})
        chain.append({"step": "execution_filter", "result": exec_reason or "ok", "passed": exec_pass})

        return chain

    @staticmethod
    def _latest_value(value: Any, default: float) -> float:
        if value is None:
            return default
        if hasattr(value, "iloc"):
            try:
                if len(value) == 0:
                    return default
                return float(value.iloc[-1])
            except Exception:
                return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default


decision_service = DecisionStatusService()
