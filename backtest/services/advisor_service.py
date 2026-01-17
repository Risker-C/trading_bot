"""
AI建议生成器 - 基于回测结果生成优化建议
"""
from typing import Dict, List, Any


class AdvisorService:
    """AI建议生成服务"""

    @staticmethod
    def generate_recommendations(
        metrics: Dict[str, Any],
        scenario_analysis: Dict[str, Dict[str, Any]],
        trades: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        生成优化建议

        Args:
            metrics: 回测指标
            scenario_analysis: 场景分析结果
            trades: 交易记录

        Returns:
            建议列表
        """
        recommendations = []

        # 1. 胜率分析
        win_rate = metrics.get('win_rate', 0)
        if win_rate < 0.4:
            recommendations.append({
                'type': 'strategy',
                'priority': 'high',
                'title': '胜率过低',
                'content': f'当前胜率仅{win_rate*100:.1f}%，建议优化入场条件，提高信号质量。可以考虑增加过滤器或调整参数阈值。',
                'action': '调整策略参数以提高信号准确性'
            })

        # 2. 盈亏比分析
        profit_factor = metrics.get('profit_factor', 0)
        if profit_factor < 1.5:
            recommendations.append({
                'type': 'risk',
                'priority': 'high',
                'title': '盈亏比不足',
                'content': f'当前盈亏比为{profit_factor:.2f}，建议优化止盈止损策略。可以考虑扩大止盈目标或收紧止损。',
                'action': '调整风险收益比，扩大盈利空间'
            })

        # 3. 最大回撤分析
        max_drawdown = metrics.get('max_drawdown', 0)
        if max_drawdown > 0.2:
            recommendations.append({
                'type': 'risk',
                'priority': 'critical',
                'title': '回撤过大',
                'content': f'最大回撤达到{max_drawdown*100:.1f}%，风险过高。建议降低仓位或增加风控条件。',
                'action': '降低单笔交易仓位或增加止损保护'
            })

        # 4. 场景适应性分析
        if scenario_analysis:
            best_scenario = max(scenario_analysis.items(), key=lambda x: x[1].get('win_rate', 0))
            worst_scenario = min(scenario_analysis.items(), key=lambda x: x[1].get('win_rate', 0))

            if best_scenario[1].get('win_rate', 0) - worst_scenario[1].get('win_rate', 0) > 0.3:
                recommendations.append({
                    'type': 'parameter',
                    'priority': 'medium',
                    'title': '场景适应性差异大',
                    'content': f'策略在{best_scenario[0]}表现最好（胜率{best_scenario[1]["win_rate"]*100:.1f}%），'
                              f'但在{worst_scenario[0]}表现较差（胜率{worst_scenario[1]["win_rate"]*100:.1f}%）。'
                              f'建议添加市场状态过滤器，仅在适合的市场环境下交易。',
                    'action': f'添加市场状态检测，避免在{worst_scenario[0]}环境下开仓'
                })

        # 5. 交易频率分析
        total_trades = metrics.get('total_trades', 0)
        if total_trades < 10:
            recommendations.append({
                'type': 'parameter',
                'priority': 'medium',
                'title': '交易次数过少',
                'content': f'回测期间仅产生{total_trades}笔交易，样本量不足。建议放宽入场条件或延长回测周期。',
                'action': '调整参数以增加交易频率，获得更多样本'
            })
        elif total_trades > 500:
            recommendations.append({
                'type': 'parameter',
                'priority': 'low',
                'title': '交易频率过高',
                'content': f'回测期间产生{total_trades}笔交易，可能存在过度交易。建议提高入场门槛。',
                'action': '收紧入场条件，减少低质量信号'
            })

        # 6. 夏普比率分析
        sharpe = metrics.get('sharpe', 0)
        if sharpe < 1.0:
            recommendations.append({
                'type': 'strategy',
                'priority': 'high',
                'title': '风险调整后收益不足',
                'content': f'夏普比率为{sharpe:.2f}，低于1.0。建议优化策略以提高稳定性和收益率。',
                'action': '提高策略稳定性，降低收益波动'
            })

        # 按优先级排序
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 999))

        return recommendations

    @staticmethod
    def generate_summary(metrics: Dict[str, Any]) -> str:
        """生成回测摘要"""
        total_return = metrics.get('total_return', 0)
        win_rate = metrics.get('win_rate', 0)
        sharpe = metrics.get('sharpe', 0)
        max_drawdown = metrics.get('max_drawdown', 0)

        if total_return > 20 and sharpe > 1.5 and max_drawdown < 0.15:
            grade = '优秀'
            summary = '策略表现优异，收益稳定且风险可控。'
        elif total_return > 10 and sharpe > 1.0 and max_drawdown < 0.25:
            grade = '良好'
            summary = '策略表现良好，但仍有优化空间。'
        elif total_return > 0 and sharpe > 0.5:
            grade = '一般'
            summary = '策略盈利但不稳定，需要进一步优化。'
        else:
            grade = '较差'
            summary = '策略表现不佳，建议重新设计或调整参数。'

        return f'【{grade}】{summary} 总收益率{total_return:.2f}%，胜率{win_rate*100:.1f}%，夏普比率{sharpe:.2f}，最大回撤{max_drawdown*100:.1f}%。'
