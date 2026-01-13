"""
市场数据格式化工具
提供Dashboard和Trace两种展示格式
"""
from typing import Dict
from datetime import datetime


class MarketFormatter:
    """市场数据格式化工具"""

    # ANSI颜色代码
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @staticmethod
    def format_dashboard(snapshot: Dict) -> str:
        """
        全景看板格式
        紧凑布局，一屏显示所有核心信息
        """
        lines = []

        # 标题
        lines.append("=" * 80)
        lines.append(f"{MarketFormatter.BOLD}市场快照 - 全景看板{MarketFormatter.RESET}")
        lines.append("=" * 80)

        # 基本信息
        lines.append(f"交易对: {snapshot['symbol']}")
        lines.append(f"时间: {snapshot['timestamp']}")
        lines.append("")

        # 多时间周期数据
        for tf, data in snapshot['timeframes'].items():
            if 'error' in data:
                lines.append(f"{MarketFormatter.RED}[{tf}] 数据获取失败: {data['error']}{MarketFormatter.RESET}")
                continue

            lines.append(f"{MarketFormatter.BOLD}━━━ {tf} 周期 ━━━{MarketFormatter.RESET}")
            lines.extend(MarketFormatter._format_timeframe_data(data))
            lines.append("")

        # 共识分析
        lines.append(f"{MarketFormatter.BOLD}━━━ 共识分析 ━━━{MarketFormatter.RESET}")
        lines.extend(MarketFormatter._format_consensus(snapshot['consensus']))

        lines.append("=" * 80)

        return "\n".join(lines)

    @staticmethod
    def _format_timeframe_data(data: Dict) -> list:
        """格式化单个时间周期数据"""
        lines = []

        # 价格
        price = data['price']
        change_color = MarketFormatter.GREEN if price['change_24h'] > 0 else MarketFormatter.RED
        lines.append(f"价格: {price['current']:.2f} USDT ({change_color}{price['change_24h']:+.2f}%{MarketFormatter.RESET})")

        # 市场状态
        regime = data['market_regime']
        state_str = str(regime['state']).lower()
        state_color = {
            'trending': MarketFormatter.GREEN,
            'ranging': MarketFormatter.YELLOW,
            'transitioning': MarketFormatter.CYAN
        }.get(state_str, MarketFormatter.WHITE)
        lines.append(f"市场状态: {state_color}{regime['state']}{MarketFormatter.RESET} (置信度: {regime['confidence']:.1%})")

        # 关键指标
        ind = data['indicators']
        lines.append(f"ADX: {ind['adx']['adx']:.1f} | RSI: {ind['rsi']:.1f} | BB宽度: {ind['bollinger']['width_pct']:.2f}%")

        # 策略信号
        signals = data['strategy_signals']
        if signals:
            signal_summary = f"{len(signals)}个信号"
            lines.append(f"策略信号: {signal_summary}")
        else:
            lines.append(f"{MarketFormatter.YELLOW}策略信号: 无{MarketFormatter.RESET}")

        return lines

    @staticmethod
    def _format_consensus(consensus: Dict) -> list:
        """格式化共识分析"""
        lines = []

        if not consensus.get('enabled'):
            lines.append("共识信号: 未启用")
            return lines

        if 'error' in consensus:
            lines.append(f"{MarketFormatter.RED}共识分析失败: {consensus['error']}{MarketFormatter.RESET}")
            return lines

        result = consensus.get('result', 'unknown')
        if result == 'no_signal':
            lines.append(f"{MarketFormatter.YELLOW}共识结果: 无信号{MarketFormatter.RESET}")
            lines.append(f"原因: {consensus.get('reason', 'N/A')}")
        elif result == 'consensus':
            lines.append(f"{MarketFormatter.GREEN}共识结果: 达成共识{MarketFormatter.RESET}")
            lines.append(f"多头: {consensus.get('long_count', 0)} | 空头: {consensus.get('short_count', 0)} | 一致性: {consensus.get('agreement', 0):.1%}")
        else:
            lines.append(f"{MarketFormatter.YELLOW}共识结果: 未达成共识{MarketFormatter.RESET}")
            lines.append(f"原因: {consensus.get('reason', 'N/A')}")

        return lines
