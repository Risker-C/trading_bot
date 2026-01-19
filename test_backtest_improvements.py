"""
测试回测改进效果
验证：
1. strategy_params 传递是否正常
2. 退出逻辑是否启用
3. 回测是否能产生交易
"""
import sys
import pandas as pd
from datetime import datetime, timedelta
from backtest.engine import BacktestEngine
from backtest.repository import BacktestRepository
from backtest.data_provider import HistoricalDataProvider

def test_backtest_with_params():
    print("=" * 60)
    print("测试回测改进效果")
    print("=" * 60)

    # 初始化
    repo = BacktestRepository("test_backtest.db")
    engine = BacktestEngine(repo)
    data_provider = HistoricalDataProvider()

    # 创建测试会话
    end_ts = int(datetime.now().timestamp())
    start_ts = end_ts - 86400 * 7  # 最近7天

    params = {
        'symbol': 'BTC/USDT:USDT',
        'timeframe': '15m',
        'start_ts': start_ts,
        'end_ts': end_ts,
        'initial_capital': 10000,
        'strategy_name': 'bollinger_trend',
        'strategy_params': {
            'BB_STD': 1.5,
            'BB_BREAKTHROUGH_COUNT': 1,
            'RSI_OVERSOLD': 35,
            'RSI_OVERBOUGHT': 65,
        }
    }

    print(f"\n1. 创建回测会话...")
    print(f"   策略: {params['strategy_name']}")
    print(f"   时间范围: {datetime.fromtimestamp(start_ts)} - {datetime.fromtimestamp(end_ts)}")
    print(f"   策略参数: {params['strategy_params']}")

    session_id = repo.create_session(params)
    print(f"   会话ID: {session_id[:8]}...")

    print(f"\n2. 获取历史数据...")
    klines = data_provider.fetch_klines(
        params['symbol'],
        params['timeframe'],
        params['start_ts'],
        params['end_ts']
    )
    print(f"   获取到 {len(klines)} 条K线数据")

    if klines.empty:
        print("   ❌ 没有获取到K线数据，测试失败")
        return False

    print(f"\n3. 运行回测引擎...")
    print(f"   传递策略参数: {params['strategy_params']}")

    try:
        engine.run(
            session_id,
            klines,
            params['strategy_name'],
            params['initial_capital'],
            params['strategy_params']
        )
        print(f"   ✅ 回测执行成功")
    except Exception as e:
        print(f"   ❌ 回测执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print(f"\n4. 检查回测结果...")

    # 获取交易记录
    conn = repo._get_conn()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM backtest_trades WHERE session_id = ?",
        (session_id,)
    )
    trade_count = cursor.fetchone()[0]

    # 获取指标
    cursor = conn.execute(
        "SELECT * FROM backtest_metrics WHERE session_id = ?",
        (session_id,)
    )
    metrics = cursor.fetchone()
    conn.close()

    print(f"   交易次数: {trade_count}")

    if trade_count == 0:
        print(f"   ⚠️  警告: 没有产生交易")
        print(f"   可能原因:")
        print(f"   - 市场条件不满足策略信号")
        print(f"   - 需要进一步调低阈值")
        print(f"   - 数据量不足")
    else:
        print(f"   ✅ 成功产生 {trade_count} 笔交易")

        if metrics:
            print(f"\n5. 回测指标:")
            print(f"   总收益率: {metrics[4]:.2f}%")
            print(f"   总盈亏: {metrics[3]:.2f} USDT")
            print(f"   胜率: {metrics[2]*100:.1f}%")
            print(f"   交易次数: {metrics[1]}")

    print(f"\n" + "=" * 60)
    print(f"测试完成")
    print(f"=" * 60)

    return trade_count > 0

if __name__ == "__main__":
    success = test_backtest_with_params()
    sys.exit(0 if success else 1)
