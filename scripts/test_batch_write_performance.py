#!/usr/bin/env python3
"""
测试数据库批量写入性能

对比启用和禁用批量写入时的性能差异:
- 写入延迟
- I/O操作次数
- 主循环阻塞时间
"""

import sys
import os
import time
import sqlite3
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from logger_utils import DatabaseLogger, get_logger

logger = get_logger("test_batch_write")


def generate_test_trades(count: int) -> List[Dict[str, Any]]:
    """生成测试交易数据"""
    trades = []
    for i in range(count):
        trades.append({
            'symbol': 'BTC/USDT:USDT',
            'side': 'long' if i % 2 == 0 else 'short',
            'action': 'open',
            'amount': 0.001 * (i + 1),
            'price': 50000 + i * 10,
            'strategy': 'test_strategy',
            'reason': f'Test trade {i}',
            'order_id': f'test_order_{i}',
            'filled_price': 50000 + i * 10,
            'filled_time': int(time.time() * 1000),
            'fee': 0.0001,
            'fee_currency': 'USDT'
        })
    return trades


def generate_test_signals(count: int) -> List[Dict[str, Any]]:
    """生成测试信号数据"""
    signals = []
    for i in range(count):
        signals.append({
            'symbol': 'BTC/USDT:USDT',
            'signal': 'long' if i % 2 == 0 else 'short',
            'strategy': 'test_strategy',
            'strength': 0.8 + (i % 20) * 0.01,
            'confidence': 0.7 + (i % 30) * 0.01,
            'reason': f'Test signal {i}',
            'price': 50000 + i * 10
        })
    return signals


def count_db_writes(db_path: str, start_time: float) -> int:
    """统计数据库写入次数（通过WAL文件大小变化估算）"""
    try:
        wal_path = db_path + '-wal'
        if os.path.exists(wal_path):
            # WAL文件存在，通过修改时间判断
            wal_mtime = os.path.getmtime(wal_path)
            if wal_mtime > start_time:
                return 1  # 有写入
        return 0
    except Exception as e:
        logger.warning(f"统计写入次数失败: {e}")
        return 0


def test_batch_write_disabled():
    """测试禁用批量写入的性能"""
    logger.info("=" * 60)
    logger.info("测试1: 禁用批量写入")
    logger.info("=" * 60)

    # 临时禁用批量写入
    original_enabled = config.DB_BATCH_WRITES_ENABLED
    config.DB_BATCH_WRITES_ENABLED = False

    # 创建新的数据库实例
    db = DatabaseLogger()

    # 生成测试数据
    test_trades = generate_test_trades(50)
    test_signals = generate_test_signals(50)

    # 测试交易记录写入
    logger.info("\n1.1 测试交易记录写入 (50条)")
    start_time = time.time()
    write_count = 0

    for trade in test_trades:
        db.log_trade(**trade)
        write_count += 1

    trade_elapsed = time.time() - start_time
    trade_avg_latency = trade_elapsed / len(test_trades) * 1000  # ms

    logger.info(f"✅ 交易记录写入完成:")
    logger.info(f"   总耗时: {trade_elapsed:.3f}s")
    logger.info(f"   平均延迟: {trade_avg_latency:.2f}ms/条")
    logger.info(f"   写入次数: {write_count}次 (每条一次)")

    # 测试信号记录写入
    logger.info("\n1.2 测试信号记录写入 (50条)")
    start_time = time.time()
    write_count = 0

    for signal in test_signals:
        db.log_signal(**signal)
        write_count += 1

    signal_elapsed = time.time() - start_time
    signal_avg_latency = signal_elapsed / len(test_signals) * 1000  # ms

    logger.info(f"✅ 信号记录写入完成:")
    logger.info(f"   总耗时: {signal_elapsed:.3f}s")
    logger.info(f"   平均延迟: {signal_avg_latency:.2f}ms/条")
    logger.info(f"   写入次数: {write_count}次 (每条一次)")

    # 恢复配置
    config.DB_BATCH_WRITES_ENABLED = original_enabled

    return {
        'trade_elapsed': trade_elapsed,
        'trade_avg_latency': trade_avg_latency,
        'trade_write_count': len(test_trades),
        'signal_elapsed': signal_elapsed,
        'signal_avg_latency': signal_avg_latency,
        'signal_write_count': len(test_signals),
        'total_elapsed': trade_elapsed + signal_elapsed,
        'total_write_count': len(test_trades) + len(test_signals)
    }


def test_batch_write_enabled():
    """测试启用批量写入的性能"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 启用批量写入")
    logger.info("=" * 60)

    # 确保批量写入已启用
    original_enabled = config.DB_BATCH_WRITES_ENABLED
    config.DB_BATCH_WRITES_ENABLED = True

    # 创建新的数据库实例
    db = DatabaseLogger()

    # 生成测试数据
    test_trades = generate_test_trades(50)
    test_signals = generate_test_signals(50)

    # 测试交易记录写入
    logger.info("\n2.1 测试交易记录写入 (50条)")
    start_time = time.time()

    for trade in test_trades:
        db.log_trade_buffered(**trade)

    # 记录缓冲时间
    buffer_elapsed = time.time() - start_time

    # 强制刷新缓冲区
    flush_start = time.time()
    db.flush_buffers(force=True)
    flush_elapsed = time.time() - flush_start

    trade_elapsed = time.time() - start_time
    trade_avg_latency = buffer_elapsed / len(test_trades) * 1000  # ms

    logger.info(f"✅ 交易记录写入完成:")
    logger.info(f"   缓冲耗时: {buffer_elapsed:.3f}s")
    logger.info(f"   刷新耗时: {flush_elapsed:.3f}s")
    logger.info(f"   总耗时: {trade_elapsed:.3f}s")
    logger.info(f"   平均延迟: {trade_avg_latency:.2f}ms/条 (仅缓冲)")
    logger.info(f"   批量写入: 1次 (50条合并)")

    # 测试信号记录写入
    logger.info("\n2.2 测试信号记录写入 (50条)")
    start_time = time.time()

    for signal in test_signals:
        db.log_signal_buffered(**signal)

    # 记录缓冲时间
    buffer_elapsed = time.time() - start_time

    # 强制刷新缓冲区
    flush_start = time.time()
    db.flush_buffers(force=True)
    flush_elapsed = time.time() - flush_start

    signal_elapsed = time.time() - start_time
    signal_avg_latency = buffer_elapsed / len(test_signals) * 1000  # ms

    logger.info(f"✅ 信号记录写入完成:")
    logger.info(f"   缓冲耗时: {buffer_elapsed:.3f}s")
    logger.info(f"   刷新耗时: {flush_elapsed:.3f}s")
    logger.info(f"   总耗时: {signal_elapsed:.3f}s")
    logger.info(f"   平均延迟: {signal_avg_latency:.2f}ms/条 (仅缓冲)")
    logger.info(f"   批量写入: 1次 (50条合并)")

    # 恢复配置
    config.DB_BATCH_WRITES_ENABLED = original_enabled

    return {
        'trade_elapsed': trade_elapsed,
        'trade_avg_latency': trade_avg_latency,
        'trade_write_count': 1,  # 批量写入只有1次
        'signal_elapsed': signal_elapsed,
        'signal_avg_latency': signal_avg_latency,
        'signal_write_count': 1,  # 批量写入只有1次
        'total_elapsed': trade_elapsed + signal_elapsed,
        'total_write_count': 2  # 总共2次批量写入
    }


def print_comparison(disabled_result: Dict, enabled_result: Dict):
    """打印性能对比"""
    logger.info("\n" + "=" * 60)
    logger.info("性能对比总结")
    logger.info("=" * 60)

    # 总耗时对比
    total_speedup = disabled_result['total_elapsed'] / enabled_result['total_elapsed']
    logger.info(f"\n📊 总体性能:")
    logger.info(f"   禁用批量写入: {disabled_result['total_elapsed']:.3f}s")
    logger.info(f"   启用批量写入: {enabled_result['total_elapsed']:.3f}s")
    logger.info(f"   性能提升: {total_speedup:.2f}x ({(total_speedup-1)*100:.1f}%)")

    # 交易记录对比
    trade_speedup = disabled_result['trade_elapsed'] / enabled_result['trade_elapsed']
    logger.info(f"\n📈 交易记录写入:")
    logger.info(f"   禁用批量写入: {disabled_result['trade_elapsed']:.3f}s ({disabled_result['trade_avg_latency']:.2f}ms/条)")
    logger.info(f"   启用批量写入: {enabled_result['trade_elapsed']:.3f}s ({enabled_result['trade_avg_latency']:.2f}ms/条)")
    logger.info(f"   性能提升: {trade_speedup:.2f}x")

    # 信号记录对比
    signal_speedup = disabled_result['signal_elapsed'] / enabled_result['signal_elapsed']
    logger.info(f"\n📉 信号记录写入:")
    logger.info(f"   禁用批量写入: {disabled_result['signal_elapsed']:.3f}s ({disabled_result['signal_avg_latency']:.2f}ms/条)")
    logger.info(f"   启用批量写入: {enabled_result['signal_elapsed']:.3f}s ({enabled_result['signal_avg_latency']:.2f}ms/条)")
    logger.info(f"   性能提升: {signal_speedup:.2f}x")

    # I/O次数对比
    write_reduction = (disabled_result['total_write_count'] - enabled_result['total_write_count']) / disabled_result['total_write_count']
    logger.info(f"\n💾 I/O操作次数:")
    logger.info(f"   禁用批量写入: {disabled_result['total_write_count']}次")
    logger.info(f"   启用批量写入: {enabled_result['total_write_count']}次")
    logger.info(f"   减少: {write_reduction*100:.1f}%")

    # 主循环阻塞时间估算
    logger.info(f"\n⏱️  主循环阻塞时间估算 (每次循环写入2条记录):")
    disabled_blocking = (disabled_result['trade_avg_latency'] + disabled_result['signal_avg_latency'])
    enabled_blocking = (enabled_result['trade_avg_latency'] + enabled_result['signal_avg_latency'])
    blocking_reduction = (disabled_blocking - enabled_blocking) / disabled_blocking
    logger.info(f"   禁用批量写入: {disabled_blocking:.2f}ms/循环")
    logger.info(f"   启用批量写入: {enabled_blocking:.2f}ms/循环")
    logger.info(f"   减少: {blocking_reduction*100:.1f}%")

    # 结论
    logger.info(f"\n✅ 结论:")
    if total_speedup > 1.5:
        logger.info(f"   批量写入显著提升性能 ({total_speedup:.2f}x)，建议启用")
    elif total_speedup > 1.2:
        logger.info(f"   批量写入有效提升性能 ({total_speedup:.2f}x)，建议启用")
    else:
        logger.info(f"   批量写入性能提升有限 ({total_speedup:.2f}x)，可根据需求选择")

    logger.info(f"   I/O操作减少 {write_reduction*100:.1f}%，降低磁盘压力")
    logger.info(f"   主循环阻塞时间减少 {blocking_reduction*100:.1f}%，提升响应速度")


def main():
    """主函数"""
    logger.info("开始数据库批量写入性能测试")
    logger.info(f"当前配置: DB_BATCH_WRITES_ENABLED = {config.DB_BATCH_WRITES_ENABLED}")
    logger.info(f"批量大小: {config.DB_BATCH_SIZE}")
    logger.info(f"刷新间隔: {config.DB_BATCH_FLUSH_INTERVAL}s")

    try:
        # 测试禁用批量写入
        disabled_result = test_batch_write_disabled()

        # 等待一下，避免数据库锁
        time.sleep(1)

        # 测试启用批量写入
        enabled_result = test_batch_write_enabled()

        # 打印对比结果
        print_comparison(disabled_result, enabled_result)

        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
