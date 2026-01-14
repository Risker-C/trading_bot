"""
分析胜率低的原因
深入分析历史交易数据，找出问题所在
"""
import sys
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import statistics

from config.settings import settings as config

def analyze_trades():
    """分析历史交易数据"""

    print("=" * 80)
    print("胜率分析报告")
    print("=" * 80)
    print()

    # 连接数据库
    db_file = getattr(config, 'DB_FILE', None) or getattr(config, 'DB_PATH', 'trading_bot.db')
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. 获取所有交易记录
    cursor.execute('''
        SELECT * FROM trades
        WHERE action IN ('open', 'close')
        ORDER BY created_at ASC
    ''')

    all_trades = [dict(row) for row in cursor.fetchall()]

    if not all_trades:
        print("❌ 没有找到交易记录")
        conn.close()
        return

    print(f"📊 总交易记录数: {len(all_trades)}")
    print()

    # 2. 配对开仓和平仓，计算完整交易
    completed_trades = []
    open_positions = {}

    for trade in all_trades:
        if trade['action'] == 'open':
            # 记录开仓
            key = f"{trade['symbol']}_{trade['side']}"
            open_positions[key] = trade
        elif trade['action'] == 'close':
            # 找到对应的开仓
            key = f"{trade['symbol']}_{trade['side']}"
            if key in open_positions:
                open_trade = open_positions[key]

                # 计算持仓时间
                try:
                    open_time = datetime.strptime(trade['created_at'], '%Y-%m-%d %H:%M:%S')
                    close_time = datetime.strptime(trade['created_at'], '%Y-%m-%d %H:%M:%S')
                    holding_minutes = (close_time - open_time).total_seconds() / 60
                except:
                    holding_minutes = 0

                completed_trades.append({
                    'open_time': open_trade['created_at'],
                    'close_time': trade['created_at'],
                    'holding_minutes': holding_minutes,
                    'side': trade['side'],
                    'entry_price': open_trade['price'],
                    'exit_price': trade['price'],
                    'pnl': trade['pnl'] or 0,
                    'pnl_percent': trade['pnl_percent'] or 0,
                    'strategy': open_trade['strategy'] or 'unknown',
                    'open_reason': open_trade['reason'] or '',
                    'close_reason': trade['reason'] or '',
                    'amount': open_trade['amount']
                })

                del open_positions[key]

    if not completed_trades:
        print("❌ 没有找到完整的交易对（开仓+平仓）")
        print(f"   当前有 {len(open_positions)} 个未平仓的持仓")
        conn.close()
        return

    print(f"✅ 完整交易对数: {len(completed_trades)}")
    print()

    # 3. 基础统计
    print("=" * 80)
    print("📈 基础统计")
    print("=" * 80)

    winning_trades = [t for t in completed_trades if t['pnl'] > 0]
    losing_trades = [t for t in completed_trades if t['pnl'] < 0]
    breakeven_trades = [t for t in completed_trades if t['pnl'] == 0]

    win_rate = len(winning_trades) / len(completed_trades) * 100 if completed_trades else 0

    total_pnl = sum(t['pnl'] for t in completed_trades)
    total_wins = sum(t['pnl'] for t in winning_trades)
    total_losses = sum(t['pnl'] for t in losing_trades)

    avg_win = total_wins / len(winning_trades) if winning_trades else 0
    avg_loss = total_losses / len(losing_trades) if losing_trades else 0

    profit_factor = abs(total_wins / total_losses) if total_losses != 0 else 0

    print(f"总交易数: {len(completed_trades)}")
    print(f"盈利交易: {len(winning_trades)} ({len(winning_trades)/len(completed_trades)*100:.1f}%)")
    print(f"亏损交易: {len(losing_trades)} ({len(losing_trades)/len(completed_trades)*100:.1f}%)")
    print(f"盈亏平衡: {len(breakeven_trades)}")
    print()
    print(f"胜率: {win_rate:.1f}%")
    print(f"总盈亏: {total_pnl:.2f} USDT")
    print(f"平均盈利: {avg_win:.2f} USDT")
    print(f"平均亏损: {avg_loss:.2f} USDT")
    print(f"盈亏比: {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "盈亏比: N/A")
    print(f"盈利因子: {profit_factor:.2f}")
    print()

    # 4. 策略表现分析
    print("=" * 80)
    print("🎯 策略表现分析")
    print("=" * 80)

    strategy_stats = defaultdict(lambda: {'total': 0, 'wins': 0, 'losses': 0, 'pnl': 0})

    for trade in completed_trades:
        strategy = trade['strategy']
        strategy_stats[strategy]['total'] += 1
        strategy_stats[strategy]['pnl'] += trade['pnl']

        if trade['pnl'] > 0:
            strategy_stats[strategy]['wins'] += 1
        elif trade['pnl'] < 0:
            strategy_stats[strategy]['losses'] += 1

    print(f"{'策略':<30} {'交易数':<10} {'胜率':<10} {'总盈亏':<15}")
    print("-" * 80)

    for strategy, stats in sorted(strategy_stats.items(), key=lambda x: x[1]['total'], reverse=True):
        win_rate = stats['wins'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"{strategy:<30} {stats['total']:<10} {win_rate:<10.1f}% {stats['pnl']:<15.2f}")

    print()

    # 5. 方向分析（多空表现）
    print("=" * 80)
    print("📊 多空方向分析")
    print("=" * 80)

    long_trades = [t for t in completed_trades if t['side'] == 'long']
    short_trades = [t for t in completed_trades if t['side'] == 'short']

    long_wins = len([t for t in long_trades if t['pnl'] > 0])
    short_wins = len([t for t in short_trades if t['pnl'] > 0])

    long_win_rate = long_wins / len(long_trades) * 100 if long_trades else 0
    short_win_rate = short_wins / len(short_trades) * 100 if short_trades else 0

    long_pnl = sum(t['pnl'] for t in long_trades)
    short_pnl = sum(t['pnl'] for t in short_trades)

    print(f"做多交易: {len(long_trades)} 笔")
    print(f"  胜率: {long_win_rate:.1f}%")
    print(f"  总盈亏: {long_pnl:.2f} USDT")
    print()
    print(f"做空交易: {len(short_trades)} 笔")
    print(f"  胜率: {short_win_rate:.1f}%")
    print(f"  总盈亏: {short_pnl:.2f} USDT")
    print()

    # 6. 持仓时间分析
    print("=" * 80)
    print("⏱️  持仓时间分析")
    print("=" * 80)

    holding_times = [t['holding_minutes'] for t in completed_trades if t['holding_minutes'] > 0]

    if holding_times:
        avg_holding = statistics.mean(holding_times)
        median_holding = statistics.median(holding_times)

        print(f"平均持仓时间: {avg_holding:.1f} 分钟 ({avg_holding/60:.1f} 小时)")
        print(f"中位数持仓时间: {median_holding:.1f} 分钟 ({median_holding/60:.1f} 小时)")
        print()

        # 按持仓时间分组分析
        short_term = [t for t in completed_trades if 0 < t['holding_minutes'] <= 60]
        medium_term = [t for t in completed_trades if 60 < t['holding_minutes'] <= 240]
        long_term = [t for t in completed_trades if t['holding_minutes'] > 240]

        print("持仓时间分组:")
        print(f"  短期 (≤1小时): {len(short_term)} 笔, 胜率: {len([t for t in short_term if t['pnl']>0])/len(short_term)*100:.1f}%" if short_term else "  短期: 无数据")
        print(f"  中期 (1-4小时): {len(medium_term)} 笔, 胜率: {len([t for t in medium_term if t['pnl']>0])/len(medium_term)*100:.1f}%" if medium_term else "  中期: 无数据")
        print(f"  长期 (>4小时): {len(long_term)} 笔, 胜率: {len([t for t in long_term if t['pnl']>0])/len(long_term)*100:.1f}%" if long_term else "  长期: 无数据")
    print()

    # 7. 平仓原因分析
    print("=" * 80)
    print("🚪 平仓原因分析")
    print("=" * 80)

    close_reasons = Counter(t['close_reason'] for t in completed_trades)

    print(f"{'平仓原因':<40} {'次数':<10} {'占比':<10}")
    print("-" * 80)

    for reason, count in close_reasons.most_common():
        percentage = count / len(completed_trades) * 100
        print(f"{reason:<40} {count:<10} {percentage:<10.1f}%")

    print()

    # 8. 止损止盈触发分析
    stop_loss_trades = [t for t in completed_trades if '止损' in t['close_reason']]
    take_profit_trades = [t for t in completed_trades if '止盈' in t['close_reason']]

    print(f"止损触发: {len(stop_loss_trades)} 次 ({len(stop_loss_trades)/len(completed_trades)*100:.1f}%)")
    print(f"止盈触发: {len(take_profit_trades)} 次 ({len(take_profit_trades)/len(completed_trades)*100:.1f}%)")
    print()

    # 9. 最大连续亏损分析
    print("=" * 80)
    print("📉 连续亏损分析")
    print("=" * 80)

    max_consecutive_losses = 0
    current_consecutive_losses = 0

    for trade in completed_trades:
        if trade['pnl'] < 0:
            current_consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_consecutive_losses)
        else:
            current_consecutive_losses = 0

    print(f"最大连续亏损: {max_consecutive_losses} 次")
    print()

    # 10. 问题诊断
    print("=" * 80)
    print("🔍 问题诊断")
    print("=" * 80)
    print()

    issues = []

    # 诊断1: 胜率过低
    if win_rate < 30:
        issues.append({
            'severity': '严重',
            'issue': f'胜率过低 ({win_rate:.1f}%)',
            'analysis': '胜率低于30%说明策略的方向判断存在严重问题',
            'suggestions': [
                '检查策略信号的准确性',
                '考虑增加信号过滤条件',
                '检查是否在不适合的市场环境下交易',
                '考虑反向操作（如果胜率极低，可能方向完全相反）'
            ]
        })

    # 诊断2: 盈亏比分析
    if avg_loss != 0:
        win_loss_ratio = abs(avg_win / avg_loss)
        if win_loss_ratio < 1.5:
            issues.append({
                'severity': '中等',
                'issue': f'盈亏比不足 ({win_loss_ratio:.2f})',
                'analysis': '平均盈利不足以覆盖平均亏损，即使提高胜率也难以盈利',
                'suggestions': [
                    f'当前止盈: {config.TAKE_PROFIT_PCT*100:.1f}%, 止损: {config.STOP_LOSS_PCT*100:.1f}%',
                    '考虑扩大止盈目标或收紧止损',
                    '启用移动止损保护利润',
                    '避免过早止盈'
                ]
            })

    # 诊断3: 止损触发过多
    if len(stop_loss_trades) / len(completed_trades) > 0.6:
        issues.append({
            'severity': '严重',
            'issue': f'止损触发过于频繁 ({len(stop_loss_trades)/len(completed_trades)*100:.1f}%)',
            'analysis': '超过60%的交易触发止损，说明入场时机或止损设置有问题',
            'suggestions': [
                '检查入场信号的质量',
                '考虑放宽止损（当前: {:.1f}%）'.format(config.STOP_LOSS_PCT*100),
                '增加趋势确认条件',
                '避免在震荡市场交易'
            ]
        })

    # 诊断4: 策略表现差异
    best_strategy = max(strategy_stats.items(), key=lambda x: x[1]['pnl'])[0] if strategy_stats else None
    worst_strategy = min(strategy_stats.items(), key=lambda x: x[1]['pnl'])[0] if strategy_stats else None

    if best_strategy and worst_strategy and len(strategy_stats) > 1:
        best_pnl = strategy_stats[best_strategy]['pnl']
        worst_pnl = strategy_stats[worst_strategy]['pnl']

        if worst_pnl < -10:  # 亏损超过10 USDT
            issues.append({
                'severity': '中等',
                'issue': f'策略 "{worst_strategy}" 表现极差',
                'analysis': f'该策略总亏损 {worst_pnl:.2f} USDT，拖累整体表现',
                'suggestions': [
                    f'考虑禁用 "{worst_strategy}" 策略',
                    f'保留表现较好的 "{best_strategy}" 策略 (盈亏: {best_pnl:.2f} USDT)',
                    '重新评估策略组合'
                ]
            })

    # 诊断5: 多空表现差异
    if abs(long_win_rate - short_win_rate) > 20:
        better_side = 'long' if long_win_rate > short_win_rate else 'short'
        worse_side = 'short' if better_side == 'long' else 'long'

        issues.append({
            'severity': '中等',
            'issue': f'多空表现差异大 (做多: {long_win_rate:.1f}%, 做空: {short_win_rate:.1f}%)',
            'analysis': f'做{better_side}表现明显优于做{worse_side}',
            'suggestions': [
                f'在当前市场环境下，优先做{better_side}',
                f'检查做{worse_side}的信号质量',
                '考虑只在明确趋势下做单向交易'
            ]
        })

    # 输出诊断结果
    if issues:
        for i, issue in enumerate(issues, 1):
            print(f"问题 {i}: [{issue['severity']}] {issue['issue']}")
            print(f"分析: {issue['analysis']}")
            print("建议:")
            for suggestion in issue['suggestions']:
                print(f"  • {suggestion}")
            print()
    else:
        print("✅ 未发现明显问题（但胜率仍需提高）")
        print()

    # 11. 配置建议
    print("=" * 80)
    print("⚙️  配置优化建议")
    print("=" * 80)
    print()

    print("当前配置:")
    print(f"  止损: {config.STOP_LOSS_PCT*100:.1f}%")
    print(f"  止盈: {config.TAKE_PROFIT_PCT*100:.1f}%")
    print(f"  移动止损: {config.TRAILING_STOP_PCT*100:.1f}%")
    print(f"  杠杆: {config.LEVERAGE}x")
    print(f"  仓位比例: {config.POSITION_SIZE_PCT*100:.1f}%")
    print()

    print("优化建议:")

    # 基于盈亏比给建议
    if avg_loss != 0:
        win_loss_ratio = abs(avg_win / avg_loss)
        if win_loss_ratio < 1.5:
            print(f"  • 提高止盈目标: {config.TAKE_PROFIT_PCT*100:.1f}% → {config.TAKE_PROFIT_PCT*100*1.5:.1f}%")
            print(f"  • 或收紧止损: {config.STOP_LOSS_PCT*100:.1f}% → {config.STOP_LOSS_PCT*100*0.7:.1f}%")

    # 基于胜率给建议
    if win_rate < 30:
        print(f"  • 降低杠杆: {config.LEVERAGE}x → {max(3, config.LEVERAGE//2)}x")
        print(f"  • 减少仓位: {config.POSITION_SIZE_PCT*100:.1f}% → {config.POSITION_SIZE_PCT*100*0.5:.1f}%")
        print("  • 增加信号过滤条件（提高信号质量）")

    # 基于止损频率给建议
    if len(stop_loss_trades) / len(completed_trades) > 0.6:
        print(f"  • 适度放宽止损: {config.STOP_LOSS_PCT*100:.1f}% → {config.STOP_LOSS_PCT*100*1.3:.1f}%")
        print("  • 增加趋势确认（避免假突破）")

    print()

    conn.close()

    print("=" * 80)
    print("分析完成")
    print("=" * 80)


if __name__ == "__main__":
    try:
        analyze_trades()
    except Exception as e:
        print(f"❌ 分析过程出错: {e}")
        import traceback
        traceback.print_exc()
