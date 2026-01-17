"""
分析服务 - 整合场景识别、AI建议、报告生成
"""
import json
from typing import Dict, List, Any
from datetime import datetime

from backtest.domain.interfaces import IDataRepository
from backtest.services.scenario_analyzer import ScenarioAnalyzer
from backtest.services.advisor_service import AdvisorService


class AnalysisService:
    """分析服务"""

    def __init__(self, repo: IDataRepository):
        self.repo = repo
        self.scenario_analyzer = ScenarioAnalyzer()
        self.advisor = AdvisorService()

    async def analyze_backtest_run(
        self,
        run_id: str,
        klines=None,
        trades: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析回测运行

        Args:
            run_id: 回测运行ID
            klines: K线数据（可选）
            trades: 交易记录（可选）

        Returns:
            完整分析报告
        """
        # 获取指标
        conn = self.repo._get_conn()
        try:
            cursor = conn.execute("""
                SELECT total_trades, win_rate, total_pnl, total_return,
                       max_drawdown, sharpe, sortino, profit_factor,
                       expectancy, avg_win, avg_loss
                FROM backtest_metrics WHERE run_id = ?
            """, (run_id,))

            row = cursor.fetchone()
            if not row:
                return {'error': '未找到回测指标'}

            metrics = {
                'total_trades': row[0],
                'win_rate': row[1],
                'total_pnl': row[2],
                'total_return': row[3],
                'max_drawdown': row[4],
                'sharpe': row[5],
                'sortino': row[6],
                'profit_factor': row[7],
                'expectancy': row[8],
                'avg_win': row[9],
                'avg_loss': row[10]
            }
        finally:
            conn.close()

        # 场景分析（如果提供了K线和交易数据）
        scenario_analysis = {}
        if klines is not None and trades is not None:
            scenario_analysis = self.scenario_analyzer.analyze_by_scenario(
                trades, klines
            )

        # 生成建议
        recommendations = self.advisor.generate_recommendations(
            metrics, scenario_analysis, trades or []
        )

        # 生成摘要
        summary = self.advisor.generate_summary(metrics)

        # 保存报告
        report_id = await self._save_report(run_id, summary, recommendations)

        return {
            'report_id': report_id,
            'run_id': run_id,
            'summary': summary,
            'metrics': metrics,
            'scenario_analysis': scenario_analysis,
            'recommendations': recommendations
        }

    async def _save_report(
        self,
        run_id: str,
        summary: str,
        recommendations: List[Dict[str, str]]
    ) -> str:
        """保存分析报告"""
        import uuid
        report_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        conn = self.repo._get_conn()
        try:
            conn.execute("""
                INSERT INTO backtest_reports
                (id, run_id, summary, recommendations, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                report_id,
                run_id,
                summary,
                json.dumps(recommendations),
                now
            ))
            conn.commit()
            return report_id
        finally:
            conn.close()

    async def get_heatmap_data(
        self,
        job_id: str,
        param_x: str,
        param_y: str,
        target_metric: str = 'sharpe'
    ) -> Dict[str, Any]:
        """
        获取3D热力图数据

        Args:
            job_id: 优化任务ID
            param_x: X轴参数名
            param_y: Y轴参数名
            target_metric: 目标指标

        Returns:
            热力图数据（x, y, z坐标数组）
        """
        conn = self.repo._get_conn()
        try:
            # 获取优化结果
            cursor = conn.execute("""
                SELECT p.params, r.score, m.sharpe, m.total_return, m.max_drawdown
                FROM optimization_results r
                JOIN parameter_sets p ON r.param_set_id = p.id
                LEFT JOIN backtest_metrics m ON r.run_id = m.run_id
                WHERE r.job_id = ?
                ORDER BY r.rank
            """, (job_id,))

            rows = cursor.fetchall()

            if not rows:
                return {'x': [], 'y': [], 'z': []}

            # 解析数据
            x_values = []
            y_values = []
            z_values = []

            for row in rows:
                try:
                    # 尝试 JSON 解析
                    params = json.loads(row[0]) if row[0] else {}
                except (json.JSONDecodeError, TypeError):
                    # 降级：尝试 eval（仅用于历史数据兼容）
                    try:
                        params = eval(row[0]) if row[0] else {}
                    except:
                        # 完全失败，跳过此记录
                        continue

                try:
                    score = row[1]

                    if param_x in params and param_y in params:
                        x_values.append(float(params[param_x]))
                        y_values.append(float(params[param_y]))
                        z_values.append(float(score))
                except:
                    continue

            return {
                'x': x_values,
                'y': y_values,
                'z': z_values,
                'param_x': param_x,
                'param_y': param_y,
                'metric': target_metric
            }
        finally:
            conn.close()
