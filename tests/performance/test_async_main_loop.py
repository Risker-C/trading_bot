#!/usr/bin/env python3
"""
测试脚本：验证异步主循环实现
Phase 5.3.3: 改造 bot.py 主循环为异步
"""

import sys
import ast
import time

def test_syntax():
    """测试 bot.py 语法是否正确"""
    print("=" * 60)
    print("测试 1: 验证 bot.py 语法")
    print("=" * 60)
    
    try:
        with open('/root/trading_bot/bot.py', 'r', encoding='utf-8') as f:
            code = f.read()
        
        ast.parse(code)
        print("✅ bot.py 语法验证通过")
        return True
    except SyntaxError as e:
        print(f"❌ bot.py 语法错误: {e}")
        print(f"   行号: {e.lineno}")
        print(f"   位置: {e.offset}")
        return False

def test_async_methods_exist():
    """测试异步方法是否存在"""
    print("\n" + "=" * 60)
    print("测试 2: 验证异步方法是否存在")
    print("=" * 60)
    
    with open('/root/trading_bot/bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    methods_to_check = [
        'async def start_async',
        'async def _main_loop_async',
        'asyncio.run(self.start_async())',
        'await self._main_loop_async()',
        'await asyncio.sleep'
    ]
    
    all_found = True
    for method in methods_to_check:
        if method in content:
            print(f"✅ 找到: {method}")
        else:
            print(f"❌ 未找到: {method}")
            all_found = False
    
    return all_found

def test_config_switch():
    """测试配置开关是否存在"""
    print("\n" + "=" * 60)
    print("测试 3: 验证配置开关")
    print("=" * 60)
    
    try:
        with open('/root/trading_bot/config.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'USE_ASYNC_MAIN_LOOP' in content:
            print("✅ 找到配置开关: USE_ASYNC_MAIN_LOOP")
            
            # 检查默认值
            if 'USE_ASYNC_MAIN_LOOP = False' in content:
                print("✅ 默认值正确: False (向后兼容)")
            else:
                print("⚠️  默认值不是 False")
            
            return True
        else:
            print("❌ 未找到配置开关: USE_ASYNC_MAIN_LOOP")
            return False
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return False

def test_import_asyncio():
    """测试 asyncio 导入是否存在"""
    print("\n" + "=" * 60)
    print("测试 4: 验证 asyncio 导入")
    print("=" * 60)
    
    with open('/root/trading_bot/bot.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 检查前20行是否有 asyncio 导入
    for i, line in enumerate(lines[:20]):
        if 'import asyncio' in line:
            print(f"✅ 找到 asyncio 导入 (行 {i+1})")
            return True
    
    print("❌ 未找到 asyncio 导入")
    return False

def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "=" * 60)
    print("测试 5: 验证向后兼容性")
    print("=" * 60)
    
    with open('/root/trading_bot/bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查原有的 _main_loop 方法是否保留
    if 'def _main_loop(self):' in content:
        print("✅ 原有同步 _main_loop 方法已保留")
    else:
        print("❌ 原有同步 _main_loop 方法丢失")
        return False
    
    # 检查原有的 start 方法是否保留同步逻辑
    if 'time.sleep(check_interval)' in content:
        print("✅ 原有同步 sleep 逻辑已保留")
    else:
        print("❌ 原有同步 sleep 逻辑丢失")
        return False
    
    return True

def test_performance_monitoring():
    """测试性能监控日志是否添加"""
    print("\n" + "=" * 60)
    print("测试 6: 验证性能监控日志")
    print("=" * 60)
    
    with open('/root/trading_bot/bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('main_loop_async', '异步循环性能指标'),
        ('[异步]', '异步模式标识'),
        ('异步模式运行时长', '异步运行时长统计')
    ]
    
    all_found = True
    for keyword, description in checks:
        if keyword in content:
            print(f"✅ 找到: {description}")
        else:
            print(f"❌ 未找到: {description}")
            all_found = False
    
    return all_found

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Phase 5.3.3: 异步主循环实现验证")
    print("=" * 60)
    
    tests = [
        ("语法验证", test_syntax),
        ("异步方法存在性", test_async_methods_exist),
        ("配置开关", test_config_switch),
        ("asyncio 导入", test_import_asyncio),
        ("向后兼容性", test_backward_compatibility),
        ("性能监控", test_performance_monitoring)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 执行失败: {e}")
            results.append((name, False))
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print("\n" + "-" * 60)
    print(f"总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！异步主循环实现成功！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败，请检查实现")
        return 1

if __name__ == '__main__':
    sys.exit(main())
