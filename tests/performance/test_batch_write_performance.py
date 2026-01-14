#!/usr/bin/env python3
"""
测试批量写入性能
对比启用/禁用批量写入的性能差异
"""
import time
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from logger_utils import get_logger, db

logger = get_logger("test_batch_write")


def test_batch_write_performance():
    """测试批量写入性能"""
    print("=" * 60)
    print("批量写入性能测试")
    print("=" * 60)

    # 检查当前配置
    batch_enabled = getattr(config, 'DB_BATCH_WRITES_ENABLED', False)
    batch_size = getattr(config, 'DB_BATCH_SIZE', 20)
    flush_interval = getattr(config, 'DB_BATCH_FLUSH_INTERVAL', 5)

    print(f"\n当前配置:")
    print(f"  批量写入: {'启用' if batch_enabled else '禁用'}")
    print(f"  批量大小: {batch_size}")
    print(f"  刷新间隔: {flush_interval}秒")

    # 测试参数
    num_trades = 100
    num_signals = 100

    print(f"\n测试参数:")
    print(f"  交易记录数: {num_trades}")
    print(f"  信号记录数: {num_signals}")

    # 测试交易记录写入
    print(f"\n{'='*60}")
    print("测试1: 交易记录写入")
    print(f"{'='*60}")

    start_time = time.time()
    trade_write_times = []

    for i in range(num_trades):
        write_start = time.time()

        if batch_enabled:
            db.log_trade_buffered(
                symbol="BTC/USDT:USDT",
                side="long",
                action="open",
                amount=0.001,
                price=50000.0 + i,
                strategy="test_strategy",
                reason=f"test_trade_{i}"
            )
        else:
            db.log_trade(
                symbol="BTC/USDT:USDT",
                side="long",
                action="open",
                amount=0.001,
                price=50000.0 + i,
                strategy="test_strategy",
                reason=f"test_trade_{i}"
            )

        write_time = time.time() - write_start
        trade_write_times.append(write_time)

    # 如果启用批量写入，强制刷新
    if batch_enabled:
        flush_start = time.time()
        db.flush_buffers(force=True)
        flush_time = time.time() - flush_start
        print(f"  刷新缓冲区耗时: {flush_time*1000:.2f}ms")

    total_trade_time = time.time() - start_time
    avg_trade_time = sum(trade_write_times) / len(trade_write_times)
    max_trade_time = max(trade_write_times)
    min_trade_time = min(trade_write_times)

    print(f"  总耗时: {total_trade_time*1000:.2f}ms")
    print(f"  平均单次写入: {avg_trade_time*1000:.4f}ms")
    print(f"  最大单次写入: {max_trade_time*1000:.4f}ms")
    print(f"  最小单次写入: {min_trade_time*1000:.4f}ms")
    print(f"  吞吐量: {num_trades/total_trade_time:.2f} 条/秒")

    # 测试信号记录写入
    print(f"\n{'='*60}")
    print("测试2: 信号记录写入")
    print(f"{'='*60}")

    start_time = time.time()
    signal_write_times = []

    for i in range(num_signals):
        write_start = time.time()

        if batch_enabled:
            db.log_signal_buffered(
                strategy="test_strategy",
                signal="long",
                strength=0.8,
                confidence=0.9,
                reason=f"test_signal_{i}"
            )
        else:
            db.log_signal(
                strategy="test_strategy",
                signal="long",
                strength=0.8,
                confidence=0.9,
                reason=f"test_signal_{i}"
            )

        write_time = time.time() - write_start
        signal_write_times.append(write_time)

    # 如果启用批量写入，强制刷新
    if batch_enabled:
        flush_start = time.time()
        db.flush_buffers(force=True)
        flush_time = time.time() - flush_start
        print(f"  刷新缓冲区耗时: {flush_time*1000:.2f}ms")

    total_signal_time = time.time() - start_time
    avg_signal_time = sum(signal_write_times) / len(signal_write_times)
    max_signal_time = max(signal_write_times)
    min_signal_time = min(signal_write_times)

    print(f"  总耗时: {total_signal_time*1000:.2f}ms")
    print(f"  平均单次写入: {avg_signal_time*1000:.4f}ms")
    print(f"  最大单次写入: {max_signal_time*1000:.4f}ms")
    print(f"  最小单次写入: {min_signal_time*1000:.4f}ms")
    print(f"  吞吐量: {num_signals/total_signal_time:.2f} 条/秒")

    # 总结
    print(f"\n{'='*60}")
    print("性能总结")
    print(f"{'='*60}")

    total_time = total_trade_time + total_signal_time
    total_records = num_trades + num_signals

    print(f"  总记录数: {total_records}")
    print(f"  总耗时: {total_time*1000:.2f}ms")
    print(f"  平均每条记录: {(total_time/total_records)*1000:.4f}ms")
    print(f"  总吞吐量: {total_records/total_time:.2f} 条/秒")

    # 主循环阻塞时间估算
    print(f"\n{'='*60}")
    print("主循环影响分析")
    print(f"{'='*60}")

    # 假设每个循环周期写入2条交易记录和5条信号记录
    cycle_trades = 2
    cycle_signals = 5

    cycle_blocking_time = (avg_trade_time * cycle_trades + avg_signal_time * cycle_signals) * 1000

    print(f"  假设每周期写入: {cycle_trades}条交易 + {cycle_signals}条信号")
    print(f"  主循环阻塞时间: {cycle_blocking_time:.4f}ms")

    if batch_enabled:
        print(f"  ✅ 批量写入模式: 写入操作不阻塞，后台定期刷新")
    else:
        print(f"  ⚠️  直接写入模式: 每次写入都会阻塞主循环")

    print(f"\n{'='*60}")
    print("测试完成")
    print(f"{'='*60}\n")

    return {
        'batch_enabled': batch_enabled,
        'total_time': total_time,
        'total_records': total_records,
        'throughput': total_records / total_time,
        'avg_trade_time': avg_trade_time,
        'avg_signal_time': avg_signal_time,
        'cycle_blocking_time': cycle_blocking_time
    }


if __name__ == "__main__":
    try:
        result = test_batch_write_performance()
        sys.exit(0)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
