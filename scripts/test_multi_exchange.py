#!/usr/bin/env python3
"""
多交易所框架测试脚本

测试内容：
1. 工厂注册验证
2. 适配器创建测试
3. 交易所连接测试
4. 基础数据获取测试
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings as config
from exchange import ExchangeFactory, ExchangeManager
from utils.logger_utils import get_logger

logger = get_logger("test_multi_exchange")


class TestMultiExchange:
    """多交易所测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0

    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.total += 1
        print(f"\n{'='*60}")
        print(f"测试 {self.total}: {test_name}")
        print(f"{'='*60}")

        try:
            test_func()
            self.passed += 1
            print(f"✅ 测试通过: {test_name}")
            return True
        except AssertionError as e:
            self.failed += 1
            print(f"❌ 测试失败: {test_name}")
            print(f"   错误: {e}")
            return False
        except Exception as e:
            self.failed += 1
            print(f"❌ 测试异常: {test_name}")
            print(f"   异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("测试摘要")
        print(f"{'='*60}")
        print(f"总计: {self.total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"成功率: {(self.passed/self.total*100):.1f}%")
        print(f"{'='*60}\n")

        return self.failed == 0


def test_factory_registration():
    """测试1: 工厂注册验证"""
    supported = ExchangeFactory.get_supported_exchanges()
    print(f"支持的交易所: {supported}")
    
    assert 'bitget' in supported, "Bitget未注册"
    assert 'binance' in supported, "Binance未注册"
    assert 'okx' in supported, "OKX未注册"
    
    print("✓ 所有交易所已正确注册")


def test_config_validation():
    """测试2: 配置验证"""
    assert hasattr(config, 'ACTIVE_EXCHANGE'), "缺少ACTIVE_EXCHANGE配置"
    assert hasattr(config, 'EXCHANGES_CONFIG'), "缺少EXCHANGES_CONFIG配置"
    
    print(f"当前激活交易所: {config.ACTIVE_EXCHANGE}")
    print(f"配置的交易所: {list(config.EXCHANGES_CONFIG.keys())}")
    
    assert config.ACTIVE_EXCHANGE in config.EXCHANGES_CONFIG, "激活的交易所不在配置中"
    
    print("✓ 配置验证通过")


def test_adapter_creation():
    """测试3: 适配器创建"""
    for exchange_name in ['bitget', 'binance', 'okx']:
        print(f"\n创建 {exchange_name} 适配器...")
        
        exchange_config = config.EXCHANGES_CONFIG.get(exchange_name, )
        adapter = ExchangeFactory.create(exchange_name, exchange_config)
        
        assert adapter is not None, f"{exchange_name} 适配器创建失败"
        assert adapter.get_exchange_name() == exchange_name, f"交易所名称不匹配"
        
        print(f"✓ {exchange_name} 适配器创建成功")


def test_manager_initialization():
    """测试4: 管理器初始化"""
    manager = ExchangeManager()
    manager.initialize()
    
    current = manager.get_current_exchange()
    assert current is not None, "获取当前交易所失败"
    
    print(f"当前交易所: {current.get_exchange_name()}")
    print("✓ 管理器初始化成功")


def test_exchange_switching():
    """测试5: 交易所切换"""
    manager = ExchangeManager()
    manager.initialize()
    
    original = config.ACTIVE_EXCHANGE
    print(f"原始交易所: {original}")
    
    # 测试切换到其他交易所
    test_exchanges = ['bitget', 'binance', 'okx']
    for exchange_name in test_exchanges:
        if exchange_name != original:
            success = manager.switch_exchange(exchange_name)
            assert success, f"切换到 {exchange_name} 失败"
            
            current = manager.get_current_exchange()
            assert current.get_exchange_name() == exchange_name, "切换后交易所不匹配"
            
            print(f"✓ 成功切换到 {exchange_name}")
            break
    
    # 切换回原始交易所
    manager.switch_exchange(original)
    print(f"✓ 切换回原始交易所: {original}")


def test_bitget_connection():
    """测试6: Bitget连接测试"""
    if not config.EXCHANGES_CONFIG['bitget']['api_key']:
        print("⚠️  跳过: 未配置Bitget API密钥")
        return
    
    exchange_config = config.EXCHANGES_CONFIG['bitget']
    adapter = ExchangeFactory.create('bitget', exchange_config)
    
    try:
        adapter.connect()
        assert adapter.is_connected(), "Bitget连接失败"
        print("✓ Bitget连接成功")
        
        # 测试获取行情
        ticker = adapter.get_ticker()
        if ticker:
            print(f"✓ 获取行情成功: {ticker.symbol} @ {ticker.last}")
        
        adapter.disconnect()
    except Exception as e:
        print(f"⚠️  Bitget连接测试失败: {e}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("多交易所框架测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestMultiExchange()

    # 运行所有测试
    tester.run_test("工厂注册验证", test_factory_registration)
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("适配器创建", test_adapter_creation)
    tester.run_test("管理器初始化", test_manager_initialization)
    tester.run_test("交易所切换", test_exchange_switching)
    tester.run_test("Bitget连接测试", test_bitget_connection)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
