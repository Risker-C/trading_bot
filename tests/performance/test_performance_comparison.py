"""
性能对比测试：同步 vs 异步数据获取
"""
import time
import sys
sys.path.insert(0, '.')

import config

# 临时修改配置进行测试
original_async_fetch = getattr(config, 'USE_ASYNC_DATA_FETCH', True)

def test_sync_fetch():
    """测试同步数据获取"""
    from core.trader import BitgetTrader
    
    # 禁用异步模式
    config.USE_ASYNC_DATA_FETCH = False
    
    trader = BitgetTrader()
    
    print("\n[同步模式] 获取多时间周期数据")
    start = time.time()
    data = trader.fetch_multi_timeframe_data()
    elapsed = time.time() - start
    
    print(f"✓ 获取 {len(data)} 个时间周期")
    print(f"⏱️  耗时: {elapsed:.2f}秒")
    
    return elapsed

def test_async_fetch():
    """测试异步数据获取"""
    from core.trader import BitgetTrader
    
    # 启用异步模式
    config.USE_ASYNC_DATA_FETCH = True
    
    trader = BitgetTrader()
    
    print("\n[异步模式] 获取多时间周期数据")
    start = time.time()
    data = trader.fetch_multi_timeframe_data()
    elapsed = time.time() - start
    
    print(f"✓ 获取 {len(data)} 个时间周期")
    print(f"⏱️  耗时: {elapsed:.2f}秒")
    
    return elapsed

if __name__ == "__main__":
    print("=" * 60)
    print("性能对比测试：同步 vs 异步")
    print("=" * 60)
    
    # 测试同步模式
    sync_time = test_sync_fetch()
    
    # 测试异步模式
    async_time = test_async_fetch()
    
    # 对比结果
    print("\n" + "=" * 60)
    print("性能对比结果")
    print("=" * 60)
    print(f"同步模式耗时: {sync_time:.2f}秒")
    print(f"异步模式耗时: {async_time:.2f}秒")
    
    if async_time > 0:
        speedup = sync_time / async_time
        improvement = (1 - async_time / sync_time) * 100
        print(f"性能提升: {speedup:.2f}x")
        print(f"延迟降低: {improvement:.1f}%")
    
    # 恢复原始配置
    config.USE_ASYNC_DATA_FETCH = original_async_fetch
    
    print("\n✅ 测试完成")
