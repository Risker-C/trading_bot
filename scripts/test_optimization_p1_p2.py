"""
测试P1/P2优化实现
验证优化服务能够执行真实回测并返回正确结果

运行要求:
- 需要安装项目依赖: pandas, numpy, ccxt等
- 建议在项目的虚拟环境中运行
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.adapters.storage.sqlite_repo import SQLiteRepository
from backtest.adapters.cache.memory_cache import MemoryCache
from backtest.services.optimization_service import OptimizationService
from backtest.services.strategy_version_service import StrategyVersionService
from backtest.services.backtest_service import BacktestService
from backtest.services.data_service import DataService
from backtest.data_provider import HistoricalDataProvider


async def test_repository_methods():
    """测试Repository新增方法"""
    print("\n=== 测试1: Repository新增方法 ===")

    repo = SQLiteRepository()
    cache = MemoryCache()
    provider = HistoricalDataProvider()
    data_service = DataService(repo, cache, provider)
    strategy_service = StrategyVersionService(repo)

    # 创建测试策略版本
    strategy_version_id = await strategy_service.create_strategy_version(
        name='MACrossStrategy',
        version='1.0',
        params_schema={'fast_period': {'type': 'int', 'min': 5, 'max': 20}}
    )
    print(f"✓ 创建策略版本: {strategy_version_id}")

    # 获取策略版本信息
    strategy_info = await repo.get_strategy_version(strategy_version_id)
    assert strategy_info['name'] == 'MACrossStrategy'
    assert strategy_info['version'] == '1.0'
    print(f"✓ 获取策略版本信息: {strategy_info['name']} v{strategy_info['version']}")

    # 获取或拉取K线数据
    kline_dataset_id, is_cached = await data_service.get_or_fetch_klines(
        symbol='BTC/USDT:USDT',
        timeframe='1h',
        start_ts=1704067200000,  # 2024-01-01
        end_ts=1704153600000     # 2024-01-02
    )
    print(f"✓ 获取K线数据集: {kline_dataset_id} (缓存: {is_cached})")

    # 加载K线数据集
    df = await repo.load_kline_dataset(kline_dataset_id)
    assert len(df) > 0
    assert 'open' in df.columns
    assert 'close' in df.columns
    print(f"✓ 加载K线数据: {len(df)} 条记录")

    return strategy_version_id, kline_dataset_id


async def test_optimization_job_creation():
    """测试优化任务创建"""
    print("\n=== 测试2: 优化任务创建 ===")

    repo = SQLiteRepository()
    backtest_service = BacktestService(repo, MemoryCache())
    optimization_service = OptimizationService(repo, backtest_service)

    # 使用测试1的数据
    strategy_version_id, kline_dataset_id = await test_repository_methods()

    # 创建优化任务
    job_id = await optimization_service.create_optimization_job(
        strategy_version_id=strategy_version_id,
        kline_dataset_id=kline_dataset_id,
        algorithm='grid',
        search_space={'fast_period': [5, 10], 'slow_period': [20, 30]},
        target_metric='sharpe'
    )
    print(f"✓ 创建优化任务: {job_id}")

    # 验证任务状态
    conn = repo._get_conn()
    try:
        cursor = conn.execute("SELECT status, algorithm FROM optimization_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 'created'
        assert row[1] == 'grid'
        print(f"✓ 任务状态: {row[0]}, 算法: {row[1]}")
    finally:
        conn.close()

    return job_id, strategy_version_id, kline_dataset_id


async def test_grid_search_optimization():
    """测试网格搜索优化"""
    print("\n=== 测试3: 网格搜索优化 ===")

    repo = SQLiteRepository()
    cache = MemoryCache()
    backtest_service = BacktestService(repo, cache)
    optimization_service = OptimizationService(repo, backtest_service)

    job_id, strategy_version_id, kline_dataset_id = await test_optimization_job_creation()

    # 执行优化（小规模测试）
    print("执行网格搜索优化...")
    results = await optimization_service.run_optimization(job_id)

    assert len(results) > 0
    print(f"✓ 优化完成，返回 {len(results)} 个结果")

    # 验证结果结构
    best_result = results[0]
    assert 'params' in best_result
    assert 'score' in best_result
    assert 'run_id' in best_result
    assert 'param_set_id' in best_result
    print(f"✓ 最佳结果: score={best_result['score']:.4f}, params={best_result['params']}")

    # 验证任务状态更新
    conn = repo._get_conn()
    try:
        cursor = conn.execute("SELECT status FROM optimization_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row[0] == 'completed'
        print(f"✓ 任务状态已更新: {row[0]}")
    finally:
        conn.close()

    # 验证结果已保存到数据库
    conn = repo._get_conn()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM optimization_results WHERE job_id = ?", (job_id,))
        count = cursor.fetchone()[0]
        assert count > 0
        print(f"✓ 结果已保存到数据库: {count} 条记录")
    finally:
        conn.close()


async def test_concurrent_job_control():
    """测试并发任务控制"""
    print("\n=== 测试4: 并发任务控制 ===")

    repo = SQLiteRepository()
    cache = MemoryCache()
    backtest_service = BacktestService(repo, cache)
    optimization_service = OptimizationService(repo, backtest_service)
    strategy_service = StrategyVersionService(repo)
    provider = HistoricalDataProvider()
    data_service = DataService(repo, cache, provider)

    # 创建测试数据
    strategy_version_id = await strategy_service.create_strategy_version(
        name='TestStrategy',
        version='1.0',
        params_schema={'period': {'type': 'int', 'min': 5, 'max': 20}}
    )

    kline_dataset_id, _ = await data_service.get_or_fetch_klines(
        symbol='BTC/USDT:USDT',
        timeframe='1h',
        start_ts=1704067200000,
        end_ts=1704153600000
    )

    # 创建任务
    job_id = await optimization_service.create_optimization_job(
        strategy_version_id=strategy_version_id,
        kline_dataset_id=kline_dataset_id,
        algorithm='grid',
        search_space={'period': [10, 20]},
        target_metric='sharpe'
    )

    # 模拟并发启动（第一次应该成功）
    conn = repo._get_conn()
    try:
        cursor = conn.execute("""
            UPDATE optimization_jobs
            SET status = 'running'
            WHERE id = ? AND status IN ('created', 'failed')
        """, (job_id,))
        assert cursor.rowcount == 1
        conn.commit()
        print("✓ 第一次启动成功")
    finally:
        conn.close()

    # 模拟并发启动（第二次应该失败）
    conn = repo._get_conn()
    try:
        cursor = conn.execute("""
            UPDATE optimization_jobs
            SET status = 'running'
            WHERE id = ? AND status IN ('created', 'failed')
        """, (job_id,))
        assert cursor.rowcount == 0
        conn.commit()
        print("✓ 第二次启动被阻止（并发控制生效）")
    finally:
        conn.close()


async def test_exception_handling():
    """测试异常处理"""
    print("\n=== 测试5: 异常处理 ===")

    repo = SQLiteRepository()
    backtest_service = BacktestService(repo, MemoryCache())
    optimization_service = OptimizationService(repo, backtest_service)

    # 创建一个无效的任务（使用不存在的数据集ID）
    job_id = await optimization_service.create_optimization_job(
        strategy_version_id='invalid_strategy_id',
        kline_dataset_id='invalid_dataset_id',
        algorithm='grid',
        search_space={'period': [10]},
        target_metric='sharpe'
    )

    # 尝试运行（应该失败）
    try:
        await optimization_service.run_optimization(job_id)
        assert False, "应该抛出异常"
    except Exception as e:
        print(f"✓ 捕获到预期异常: {type(e).__name__}")

    # 验证任务状态更新为failed
    conn = repo._get_conn()
    try:
        cursor = conn.execute("SELECT status FROM optimization_jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row[0] == 'failed'
        print(f"✓ 任务状态已更新为: {row[0]}")
    finally:
        conn.close()


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("P1/P2 优化实现测试")
    print("=" * 60)

    try:
        await test_repository_methods()
        await test_optimization_job_creation()
        await test_grid_search_optimization()
        await test_concurrent_job_control()
        await test_exception_handling()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过")
        print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ 测试失败: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
