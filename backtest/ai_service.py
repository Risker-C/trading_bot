"""
Backtest AI Analysis Service
"""
import json
from typing import Dict, List, Optional
from backtest.repository import BacktestRepository
from backtest.ai_repository import AIReportRepository
from ai.claude_analyzer import ClaudeAnalyzer


class BacktestAIService:
    """Service for AI analysis of backtest results"""

    def __init__(self, db_path: str = "backtest.db"):
        self.repo = BacktestRepository(db_path)
        self.ai_repo = AIReportRepository(db_path)
        self.analyzer = ClaudeAnalyzer()

    def analyze_session(self, session_id: str) -> Dict:
        """
        Analyze a single backtest session with AI

        Returns:
            Analysis result with summary, strengths, weaknesses, recommendations
        """
        # Gather session data
        conn = self.repo._get_conn()
        try:
            # Get session info
            session_row = conn.execute(
                "SELECT * FROM backtest_sessions WHERE id = ?", (session_id,)
            ).fetchone()

            if not session_row:
                raise ValueError(f"Session {session_id} not found")

            # Get metrics
            metrics_row = conn.execute(
                "SELECT * FROM backtest_metrics WHERE session_id = ?", (session_id,)
            ).fetchone()

            # Get trade statistics
            trades_cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                    AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                    MAX(pnl) as max_win,
                    MIN(pnl) as min_loss
                FROM backtest_trades
                WHERE session_id = ? AND action = 'close'
            """, (session_id,))
            trade_stats = trades_cursor.fetchone()

        finally:
            conn.close()

        # Build analysis prompt
        metrics_data = {
            "total_return": metrics_row[4] if metrics_row else 0,
            "max_drawdown": metrics_row[5] if metrics_row else 0,
            "sharpe": metrics_row[6] if metrics_row else 0,
            "win_rate": metrics_row[2] if metrics_row else 0,
            "total_trades": trade_stats[0] if trade_stats else 0,
            "winning_trades": trade_stats[1] if trade_stats else 0,
            "losing_trades": trade_stats[2] if trade_stats else 0,
            "avg_win": trade_stats[3] if trade_stats else 0,
            "avg_loss": trade_stats[4] if trade_stats else 0,
            "max_win": trade_stats[5] if trade_stats else 0,
            "min_loss": trade_stats[6] if trade_stats else 0,
        }

        prompt = self._build_analysis_prompt(metrics_data, session_row)

        # Call AI analyzer
        if not self.analyzer.enabled:
            raise RuntimeError("AI analysis is not enabled. Please configure ANTHROPIC_AUTH_TOKEN.")

        try:
            response = self.analyzer.client.messages.create(
                model=self.analyzer.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis_text = response.content[0].text.strip()

            # Parse AI response (expecting JSON format)
            try:
                analysis_result = json.loads(analysis_text)
            except json.JSONDecodeError:
                # Fallback: treat as plain text summary
                analysis_result = {
                    "summary": analysis_text,
                    "strengths": [],
                    "weaknesses": [],
                    "recommendations": [],
                    "param_suggestions": {}
                }

            # Save report
            self.ai_repo.create_report(
                session_id=session_id,
                model_name=self.analyzer.model,
                prompt_version="v1",
                input_data=metrics_data,
                analysis_result=analysis_result
            )

            return analysis_result

        except Exception as e:
            # Re-raise exception instead of returning error dict
            raise RuntimeError(f"AI analysis failed: {str(e)}") from e

    def _build_analysis_prompt(self, metrics: Dict, session_row) -> str:
        """Build AI analysis prompt"""
        strategy_name = session_row[12] if len(session_row) > 12 else "Unknown"

        return f"""你是一名资深量化交易分析师。请分析以下回测结果，并以 JSON 格式返回分析报告。

回测策略：{strategy_name}

关键指标：
- 总收益率：{metrics['total_return']:.2f}%
- 最大回撤：{metrics['max_drawdown']:.2f}%
- 夏普比率：{metrics['sharpe']:.2f}
- 胜率：{metrics['win_rate']:.2f}%
- 总交易次数：{metrics['total_trades']}
- 盈利交易：{metrics['winning_trades']}
- 亏损交易：{metrics['losing_trades']}
- 平均盈利：${metrics['avg_win']:.2f}
- 平均亏损：${metrics['avg_loss']:.2f}
- 最大单笔盈利：${metrics['max_win']:.2f}
- 最大单笔亏损：${metrics['min_loss']:.2f}

请返回 JSON 格式的分析报告，包含以下字段：
{{
  "summary": "整体评价（2-3句话）",
  "strengths": ["优势1", "优势2", "优势3"],
  "weaknesses": ["劣势1", "劣势2", "劣势3"],
  "recommendations": ["建议1", "建议2", "建议3"],
  "param_suggestions": {{
    "止损比例": "建议值",
    "止盈比例": "建议值",
    "其他参数": "建议值"
  }}
}}

请基于数据给出专业、客观的分析。"""

    def compare_sessions(self, session_ids: List[str]) -> Dict:
        """
        Compare multiple backtest sessions

        Returns:
            Comparison analysis with best session and recommendations
        """
        if len(session_ids) < 2:
            raise ValueError("At least 2 sessions required for comparison")

        # Gather data for all sessions
        sessions_data = []
        for session_id in session_ids:
            conn = self.repo._get_conn()
            try:
                session_row = conn.execute(
                    "SELECT * FROM backtest_sessions WHERE id = ?", (session_id,)
                ).fetchone()

                metrics_row = conn.execute(
                    "SELECT * FROM backtest_metrics WHERE session_id = ?", (session_id,)
                ).fetchone()

                if session_row and metrics_row:
                    sessions_data.append({
                        "session_id": session_id,
                        "strategy_name": session_row[12] if len(session_row) > 12 else "Unknown",
                        "total_return": metrics_row[4],
                        "max_drawdown": metrics_row[5],
                        "sharpe": metrics_row[6],
                        "win_rate": metrics_row[2],
                        "total_trades": metrics_row[1],
                    })
            finally:
                conn.close()

        # Build comparison prompt
        prompt = self._build_comparison_prompt(sessions_data)

        # Call AI analyzer
        if not self.analyzer.enabled:
            raise RuntimeError("AI analysis is not enabled. Please configure ANTHROPIC_AUTH_TOKEN.")

        try:
            response = self.analyzer.client.messages.create(
                model=self.analyzer.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis_text = response.content[0].text.strip()

            try:
                comparison_result = json.loads(analysis_text)
            except json.JSONDecodeError:
                comparison_result = {
                    "summary": analysis_text,
                    "best_session_id": session_ids[0],
                    "comparison": [],
                    "recommendations": []
                }

            # Save reports for each session in the comparison group
            compare_group_id = f"compare_{int(datetime.utcnow().timestamp())}"
            for session_id in session_ids:
                self.ai_repo.create_report(
                    session_id=session_id,
                    model_name=self.analyzer.model,
                    prompt_version="v1_compare",
                    input_data={"sessions": sessions_data},
                    analysis_result=comparison_result,
                    compare_group_id=compare_group_id
                )

            comparison_result["compare_group_id"] = compare_group_id
            return comparison_result

        except Exception as e:
            # Re-raise exception instead of returning error dict
            raise RuntimeError(f"AI comparison analysis failed: {str(e)}") from e

    def _build_comparison_prompt(self, sessions_data: List[Dict]) -> str:
        """Build comparison prompt"""
        sessions_text = "\n\n".join([
            f"会话 {i+1} (ID: {s['session_id'][:8]}):\n"
            f"- 策略：{s['strategy_name']}\n"
            f"- 总收益率：{s['total_return']:.2f}%\n"
            f"- 最大回撤：{s['max_drawdown']:.2f}%\n"
            f"- 夏普比率：{s['sharpe']:.2f}\n"
            f"- 胜率：{s['win_rate']:.2f}%\n"
            f"- 交易次数：{s['total_trades']}"
            for i, s in enumerate(sessions_data)
        ])

        return f"""你是一名资深量化交易分析师。请对比分析以下 {len(sessions_data)} 个回测结果，并以 JSON 格式返回对比报告。

{sessions_text}

请返回 JSON 格式的对比报告，包含以下字段：
{{
  "summary": "整体对比评价（2-3句话）",
  "best_session_id": "表现最佳的会话ID（完整ID）",
  "comparison": [
    {{
      "session_id": "会话ID",
      "rank": 1,
      "score": 85,
      "comment": "简短评价"
    }}
  ],
  "recommendations": ["建议1", "建议2", "建议3"]
}}

请基于综合指标（收益率、风险控制、稳定性）给出专业排名和建议。"""
