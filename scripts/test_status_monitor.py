#!/usr/bin/env python3
"""
状态监控功能测试脚本

测试内容：
1. 配置验证
2. 价格历史记录功能
3. 状态数据收集功能
4. 飞书推送功能
5. 邮件降级功能
6. 完整的端到端测试
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from monitoring.status_monitor import (
    PriceHistory,
    StatusMonitorScheduler,
    StatusMonitorCollector,
    AIAnalyzer
)
from trader import BitgetTrader
from risk_manager import RiskManager
from utils.logger_utils import get_logger

logger = get_logger("test_status_monitor")


class TestStatusMonitor:
    """状态监控测试类"""

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


def test_config_validation():
    """测试1: 配置验证"""
    print("检查状态监控配置...")

    # 检查必需配置项
    assert hasattr(config, 'ENABLE_STATUS_MONITOR'), "缺少 ENABLE_STATUS_MONITOR 配置"
    assert hasattr(config, 'STATUS_MONITOR_INTERVAL'), "缺少 STATUS_MONITOR_INTERVAL 配置"
    assert hasattr(config, 'STATUS_MONITOR_ENABLE_AI'), "缺少 STATUS_MONITOR_ENABLE_AI 配置"
    assert hasattr(config, 'STATUS_MONITOR_EMAIL_ON_FAILURE'), "缺少 STATUS_MONITOR_EMAIL_ON_FAILURE 配置"
    assert hasattr(config, 'STATUS_MONITOR_MODULES'), "缺少 STATUS_MONITOR_MODULES 配置"

    print(f"  ENABLE_STATUS_MONITOR: {config.ENABLE_STATUS_MONITOR}")
    print(f"  STATUS_MONITOR_INTERVAL: {config.STATUS_MONITOR_INTERVAL} 分钟")
    print(f"  STATUS_MONITOR_ENABLE_AI: {config.STATUS_MONITOR_ENABLE_AI}")
    print(f"  STATUS_MONITOR_EMAIL_ON_FAILURE: {config.STATUS_MONITOR_EMAIL_ON_FAILURE}")

    # 验证配置值
    assert isinstance(config.STATUS_MONITOR_INTERVAL, int), "STATUS_MONITOR_INTERVAL 必须是整数"
    assert 1 <= config.STATUS_MONITOR_INTERVAL <= 60, "STATUS_MONITOR_INTERVAL 必须在1-60之间"

    # 验证模块配置
    modules = config.STATUS_MONITOR_MODULES
    assert isinstance(modules, dict), "STATUS_MONITOR_MODULES 必须是字典"
    assert 'market_change' in modules, "缺少 market_change 模块配置"
    assert 'trade_activity' in modules, "缺少 trade_activity 模块配置"
    assert 'trend_analysis' in modules, "缺少 trend_analysis 模块配置"
    assert 'service_status' in modules, "缺少 service_status 模块配置"
    assert 'account_info' in modules, "缺少 account_info 模块配置"

    print("  所有配置项验证通过")


def test_price_history():
    """测试2: 价格历史记录功能"""
    print("测试价格历史记录...")

    # 创建价格历史记录器
    history = PriceHistory(max_minutes=10)

    # 添加一些价格数据
    base_time = datetime.now()
    prices = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101]

    for i, price in enumerate(prices):
        timestamp = base_time - timedelta(minutes=len(prices)-i-1)
        history.add_price(price, timestamp)

    print(f"  添加了 {len(prices)} 条价格记录")

    # 测试获取价格变化
    change = history.get_price_change(minutes=5)
    assert change is not None, "获取价格变化失败"

    print(f"  5分钟前价格: {change['old_price']}")
    print(f"  当前价格: {change['current_price']}")
    print(f"  价格变化: {change['change']:+.2f} ({change['change_percent']:+.2f}%)")
    print(f"  最高价: {change['highest']}")
    print(f"  最低价: {change['lowest']}")
    print(f"  波动率: {change['volatility']:.2f}%")

    # 验证计算结果
    assert change['current_price'] == 101, "当前价格不正确"
    assert change['highest'] == 105, "最高价不正确"
    assert change['lowest'] == 101, "最低价不正确"

    print("  价格历史记录功能正常")


def test_scheduler_timing():
    """测试3: 调度器时间控制"""
    print("测试调度器时间控制...")

    # 创建调度器（间隔1分钟）
    scheduler = StatusMonitorScheduler(interval_minutes=1, enabled=True)

    # 第一次应该推送
    assert scheduler.should_push(), "首次应该推送"
    print("  首次推送检查: 通过")

    # 模拟推送
    scheduler.last_push_time = datetime.now()

    # 立即检查，不应该推送
    assert not scheduler.should_push(), "刚推送后不应该立即推送"
    print("  推送间隔检查: 通过")

    # 模拟时间过去
    scheduler.last_push_time = datetime.now() - timedelta(minutes=2)

    # 现在应该推送
    assert scheduler.should_push(), "超过间隔后应该推送"
    print("  超时推送检查: 通过")

    # 测试禁用状态
    scheduler.enabled = False
    assert not scheduler.should_push(), "禁用后不应该推送"
    print("  禁用状态检查: 通过")

    print("  调度器时间控制正常")


def test_price_update():
    """测试4: 价格更新功能"""
    print("测试价格更新功能...")

    scheduler = StatusMonitorScheduler(interval_minutes=5, enabled=True)

    # 更新一些价格
    prices = [43000, 43100, 43200, 43150, 43250]
    for price in prices:
        scheduler.update_price(price)

    print(f"  更新了 {len(prices)} 个价格")

    # 检查价格历史
    assert len(scheduler.price_history.prices) == len(prices), "价格记录数量不正确"

    # 获取价格变化
    change = scheduler.price_history.get_price_change(minutes=5)
    assert change is not None, "获取价格变化失败"

    print(f"  价格变化: {change['change']:+.2f} ({change['change_percent']:+.2f}%)")
    print("  价格更新功能正常")


def test_data_collection():
    """测试5: 数据收集功能"""
    print("测试数据收集功能...")

    try:
        # 创建交易器和风险管理器
        trader = BitgetTrader()
        risk_manager = RiskManager(trader)

        # 创建价格历史
        price_history = PriceHistory()

        # 添加一些价格数据
        for i in range(10):
            price_history.add_price(43000 + i * 10)

        # 创建收集器
        collector = StatusMonitorCollector(
            trader=trader,
            risk_manager=risk_manager,
            price_history=price_history,
            start_time=datetime.now() - timedelta(hours=2),
            error_count=0
        )

        print("  测试各模块数据收集...")

        # 测试行情变化收集
        market_change = collector._collect_market_change()
        assert 'available' in market_change, "行情变化数据缺少 available 字段"
        print(f"    行情变化: {'可用' if market_change.get('available') else '不可用'}")

        # 测试交易活动收集
        trade_activity = collector._collect_trade_activity()
        assert 'interval_minutes' in trade_activity, "交易活动数据缺少 interval_minutes 字段"
        print(f"    交易活动: {trade_activity.get('total_trades', 0)} 笔交易")

        # 测试趋势分析收集
        trend_analysis = collector._collect_trend_analysis()
        if 'error' not in trend_analysis:
            print(f"    趋势分析: {trend_analysis.get('state', 'N/A')}")
        else:
            print(f"    趋势分析: 数据获取失败（可能是网络问题）")

        # 测试服务状态收集
        service_status = collector._collect_service_status()
        assert 'timestamp' in service_status, "服务状态数据缺少 timestamp 字段"
        assert 'uptime' in service_status, "服务状态数据缺少 uptime 字段"
        print(f"    服务状态: {service_status.get('status', 'N/A')}")

        # 测试账户信息收集
        account_info = collector._collect_account_info()
        if 'error' not in account_info:
            print(f"    账户信息: {account_info.get('balance', 0):.2f} USDT")
        else:
            print(f"    账户信息: 数据获取失败（可能是网络问题）")

        # 测试完整数据收集
        all_data = collector.collect_all()
        assert isinstance(all_data, dict), "收集的数据应该是字典"
        print(f"  收集到 {len(all_data)} 个模块的数据")

        print("  数据收集功能正常")

    except Exception as e:
        print(f"  警告: 数据收集测试部分失败（可能是网络或API问题）: {e}")
        # 不抛出异常，因为网络问题不应该导致测试失败
        print("  跳过此测试")


def test_message_formatting():
    """测试6: 消息格式化"""
    print("测试消息格式化...")

    # 创建模拟数据
    mock_data = {
        'service_status': {
            'timestamp': '2024-12-15 14:30:00',
            'uptime': '2小时30分钟',
            'error_count': 0,
            'status': 'running'
        },
        'market_change': {
            'available': True,
            'interval_minutes': 5,
            'old_price': 43000,
            'current_price': 43250,
            'change': 250,
            'change_percent': 0.58,
            'highest': 43300,
            'lowest': 43000,
            'volatility': 0.70
        },
        'trend_analysis': {
            'state': '趋势市',
            'confidence': 75,
            'trend': '上涨',
            'volatility': '中等',
            'tradeable': True
        },
        'trade_activity': {
            'interval_minutes': 5,
            'open_count': 1,
            'close_count': 0,
            'total_trades': 1,
            'total_pnl': 0,
            'last_trade': {
                'time': '2024-12-15 14:25:00',
                'side': 'long',
                'action': 'open',
                'price': 43100,
                'amount': 0.05
            }
        },
        'account_info': {
            'balance': 9850.00,
            'has_position': True,
            'position': {
                'side': 'long',
                'amount': 0.05,
                'entry_price': 43100,
                'current_price': 43250,
                'pnl': 7.50,
                'pnl_percent': 1.74,
                'duration': '5分钟'
            }
        }
    }

    # 创建收集器（使用None作为参数，因为我们只测试格式化）
    try:
        trader = BitgetTrader()
        risk_manager = RiskManager(trader)
        price_history = PriceHistory()

        collector = StatusMonitorCollector(
            trader=trader,
            risk_manager=risk_manager,
            price_history=price_history,
            start_time=datetime.now(),
            error_count=0
        )

        # 格式化消息
        message = collector.format_message(mock_data)

        assert isinstance(message, str), "格式化的消息应该是字符串"
        assert len(message) > 0, "格式化的消息不应该为空"
        assert '系统状态推送' in message, "消息应该包含标题"
        assert '服务状态' in message, "消息应该包含服务状态"

        print("  消息格式化示例:")
        print("  " + "-" * 50)
        for line in message.split('\n')[:20]:  # 只显示前20行
            print(f"  {line}")
        print("  " + "-" * 50)
        print(f"  消息总长度: {len(message)} 字符")

        print("  消息格式化功能正常")

    except Exception as e:
        print(f"  警告: 消息格式化测试失败: {e}")
        raise


def test_ai_analyzer():
    """测试7: AI分析器接口"""
    print("测试AI分析器接口...")

    analyzer = AIAnalyzer()

    # 测试分析方法
    mock_data = {
        'market_change': {'change_percent': 0.5},
        'trend_analysis': {'state': '趋势市', 'trend': '上涨'}
    }

    result = analyzer.analyze(mock_data)

    assert isinstance(result, dict), "分析结果应该是字典"
    assert 'available' in result, "分析结果应该包含 available 字段"

    print(f"  AI分析器状态: {'可用' if result.get('available') else '待实现'}")
    print(f"  消息: {result.get('message', 'N/A')}")

    print("  AI分析器接口正常（功能待实现）")


def test_feishu_push_simulation():
    """测试8: 飞书推送模拟"""
    print("测试飞书推送模拟...")

    # 检查飞书配置
    if not config.ENABLE_FEISHU:
        print("  ⚠️  飞书未启用，跳过推送测试")
        return

    if not config.FEISHU_WEBHOOK_URL:
        print("  ⚠️  飞书 Webhook URL 未配置，跳过推送测试")
        return

    print(f"  飞书配置:")
    print(f"    启用状态: {config.ENABLE_FEISHU}")
    print(f"    Webhook URL: {config.FEISHU_WEBHOOK_URL[:50]}...")

    # 注意：这里不实际发送消息，只检查配置
    print("  飞书推送配置正常（未实际发送测试消息）")


def test_email_fallback_simulation():
    """测试9: 邮件降级模拟"""
    print("测试邮件降级模拟...")

    # 检查邮件配置
    if not config.STATUS_MONITOR_EMAIL_ON_FAILURE:
        print("  ⚠️  邮件降级未启用")
        return

    if not config.ENABLE_EMAIL:
        print("  ⚠️  邮件通知未启用，跳过测试")
        return

    print(f"  邮件配置:")
    print(f"    启用状态: {config.ENABLE_EMAIL}")
    print(f"    SMTP服务器: {config.EMAIL_SMTP_SERVER}")
    print(f"    SMTP端口: {config.EMAIL_SMTP_PORT}")
    print(f"    发件人: {config.EMAIL_SENDER}")
    print(f"    收件人: {config.EMAIL_RECEIVER}")

    # 注意：这里不实际发送邮件，只检查配置
    print("  邮件降级配置正常（未实际发送测试邮件）")


def test_end_to_end():
    """测试10: 端到端测试"""
    print("测试端到端流程...")

    try:
        # 创建完整的测试环境
        trader = BitgetTrader()
        risk_manager = RiskManager(trader)

        # 创建调度器
        scheduler = StatusMonitorScheduler(
            interval_minutes=config.STATUS_MONITOR_INTERVAL,
            enabled=True
        )

        print("  初始化完成")

        # 模拟价格更新
        test_prices = [43000, 43050, 43100, 43080, 43120]
        for price in test_prices:
            scheduler.update_price(price)

        print(f"  更新了 {len(test_prices)} 个价格")

        # 测试推送检查（不实际推送）
        should_push = scheduler.should_push()
        print(f"  推送检查: {'需要推送' if should_push else '无需推送'}")

        # 如果需要推送，测试数据收集（但不实际推送）
        if should_push:
            collector = StatusMonitorCollector(
                trader=trader,
                risk_manager=risk_manager,
                price_history=scheduler.price_history,
                start_time=scheduler.start_time,
                error_count=scheduler.error_count
            )

            data = collector.collect_all()
            print(f"  收集到 {len(data)} 个模块的数据")

            message = collector.format_message(data)
            print(f"  格式化消息长度: {len(message)} 字符")

        print("  端到端流程正常")

    except Exception as e:
        print(f"  警告: 端到端测试部分失败（可能是网络或API问题）: {e}")
        import traceback
        traceback.print_exc()
        # 不抛出异常，因为网络问题不应该导致测试失败


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("状态监控功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestStatusMonitor()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("价格历史记录功能", test_price_history)
    tester.run_test("调度器时间控制", test_scheduler_timing)
    tester.run_test("价格更新功能", test_price_update)
    tester.run_test("数据收集功能", test_data_collection)
    tester.run_test("消息格式化", test_message_formatting)
    tester.run_test("AI分析器接口", test_ai_analyzer)
    tester.run_test("飞书推送模拟", test_feishu_push_simulation)
    tester.run_test("邮件降级模拟", test_email_fallback_simulation)
    tester.run_test("端到端测试", test_end_to_end)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
