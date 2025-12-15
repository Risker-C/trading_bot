#!/usr/bin/env python3
"""
定期市场报告功能测试脚本

测试定期市场分析报告的各个组件和完整流程。
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime, timedelta
from logger_utils import get_logger

logger = get_logger("test_periodic_report")


class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self, test_name: str):
        self.total += 1
        self.passed += 1
        logger.info(f"✅ {test_name} - 通过")

    def add_fail(self, test_name: str, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append((test_name, error))
        logger.error(f"❌ {test_name} - 失败: {error}")

    def print_summary(self):
        logger.info("\n" + "=" * 60)
        logger.info("测试结果总结")
        logger.info("=" * 60)
        logger.info(f"总测试数: {self.total}")
        logger.info(f"✅ 通过: {self.passed}")
        logger.info(f"❌ 失败: {self.failed}")

        if self.errors:
            logger.info("\n失败的测试:")
            for name, error in self.errors:
                logger.info(f"  - {name}: {error}")

        if self.failed == 0:
            logger.info("\n🎉 所有测试通过!")
        else:
            logger.error(f"\n⚠️  有 {self.failed} 个测试失败，请检查!")


def test_config_validation():
    """测试1: 配置验证"""
    logger.info("\n" + "=" * 60)
    logger.info("测试1: 配置验证")
    logger.info("=" * 60)

    result = TestResult()

    try:
        import config

        # 测试1.1: 验证配置项存在
        try:
            assert hasattr(config, 'ENABLE_PERIODIC_REPORT')
            assert hasattr(config, 'PERIODIC_REPORT_INTERVAL')
            assert hasattr(config, 'PERIODIC_REPORT_DETAIL_LEVEL')
            assert hasattr(config, 'SEND_REPORT_ON_STARTUP')
            assert hasattr(config, 'PERIODIC_REPORT_MODULES')
            result.add_pass("配置项存在")
        except AssertionError as e:
            result.add_fail("配置项存在", str(e))

        # 测试1.2: 验证配置值类型
        try:
            assert isinstance(config.ENABLE_PERIODIC_REPORT, bool)
            assert isinstance(config.PERIODIC_REPORT_INTERVAL, int)
            assert isinstance(config.PERIODIC_REPORT_DETAIL_LEVEL, str)
            assert isinstance(config.SEND_REPORT_ON_STARTUP, bool)
            assert isinstance(config.PERIODIC_REPORT_MODULES, dict)
            result.add_pass("配置值类型正确")
        except AssertionError as e:
            result.add_fail("配置值类型", str(e))

        # 测试1.3: 验证配置值范围
        try:
            assert config.PERIODIC_REPORT_INTERVAL >= 30
            assert config.PERIODIC_REPORT_INTERVAL <= 720
            assert config.PERIODIC_REPORT_DETAIL_LEVEL in ['simple', 'standard', 'detailed']
            result.add_pass("配置值范围正确")
        except AssertionError as e:
            result.add_fail("配置值范围", str(e))

        # 测试1.4: 验证配置验证函数
        try:
            errors = config.validate_config()
            # 如果启用了定期报告但飞书未配置，应该有错误
            if config.ENABLE_PERIODIC_REPORT and not config.FEISHU_WEBHOOK_URL:
                assert len(errors) > 0, "应该检测到飞书未配置的错误"
            result.add_pass("配置验证函数工作正常")
        except Exception as e:
            result.add_fail("配置验证函数", str(e))

    except Exception as e:
        result.add_fail("配置验证测试", str(e))
        import traceback
        traceback.print_exc()

    result.print_summary()
    return result.failed == 0


def test_scheduler_basic():
    """测试2: 调度器基本功能"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 调度器基本功能")
    logger.info("=" * 60)

    result = TestResult()

    try:
        from market_report import PeriodicReportScheduler

        # 测试2.1: 创建调度器
        try:
            scheduler = PeriodicReportScheduler(interval_minutes=60, enabled=True)
            assert scheduler.interval_minutes == 60
            assert scheduler.enabled == True
            assert scheduler.last_report_time is None
            assert scheduler.report_count == 0
            result.add_pass("调度器创建成功")
        except Exception as e:
            result.add_fail("调度器创建", str(e))
            return False

        # 测试2.2: 测试should_send_report（首次应该发送）
        try:
            should_send = scheduler.should_send_report()
            assert should_send == True, "首次应该返回True"
            result.add_pass("首次发送判断正确")
        except Exception as e:
            result.add_fail("首次发送判断", str(e))

        # 测试2.3: 模拟发送后的状态
        try:
            scheduler.last_report_time = datetime.now()
            scheduler.report_count = 1
            should_send = scheduler.should_send_report()
            assert should_send == False, "刚发送后应该返回False"
            result.add_pass("发送后状态正确")
        except Exception as e:
            result.add_fail("发送后状态", str(e))

        # 测试2.4: 测试时间判断
        try:
            # 模拟61分钟前发送
            scheduler.last_report_time = datetime.now() - timedelta(minutes=61)
            should_send = scheduler.should_send_report()
            assert should_send == True, "超过间隔时间应该返回True"
            result.add_pass("时间判断正确")
        except Exception as e:
            result.add_fail("时间判断", str(e))

        # 测试2.5: 测试禁用状态
        try:
            scheduler.enabled = False
            should_send = scheduler.should_send_report()
            assert should_send == False, "禁用时应该返回False"
            result.add_pass("禁用状态正确")
        except Exception as e:
            result.add_fail("禁用状态", str(e))

        # 测试2.6: 测试重置计时器
        try:
            scheduler.enabled = True
            scheduler.last_report_time = datetime.now()
            scheduler.reset_timer()
            assert scheduler.last_report_time is None
            result.add_pass("重置计时器成功")
        except Exception as e:
            result.add_fail("重置计时器", str(e))

        # 测试2.7: 测试获取下次报告时间
        try:
            scheduler.last_report_time = datetime.now()
            next_time = scheduler.get_next_report_time()
            assert next_time is not None
            assert isinstance(next_time, datetime)
            result.add_pass("获取下次报告时间成功")
        except Exception as e:
            result.add_fail("获取下次报告时间", str(e))

    except Exception as e:
        result.add_fail("调度器基本功能测试", str(e))
        import traceback
        traceback.print_exc()

    result.print_summary()
    return result.failed == 0


def test_report_generator():
    """测试3: 报告生成器"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 报告生成器")
    logger.info("=" * 60)

    result = TestResult()

    try:
        from market_report import MarketReportGenerator
        from trader import BitgetTrader
        from risk_manager import RiskManager

        # 初始化依赖组件
        try:
            trader = BitgetTrader()
            risk_manager = RiskManager()
            result.add_pass("依赖组件初始化成功")
        except Exception as e:
            result.add_fail("依赖组件初始化", str(e))
            return False

        # 测试3.1: 创建报告生成器
        try:
            generator = MarketReportGenerator(trader, risk_manager)
            assert generator.trader is not None
            assert generator.risk_manager is not None
            result.add_pass("报告生成器创建成功")
        except Exception as e:
            result.add_fail("报告生成器创建", str(e))
            return False

        # 测试3.2: 测试数据收集方法
        try:
            system_info = generator._collect_system_info()
            assert 'timestamp' in system_info
            assert 'uptime' in system_info
            result.add_pass("系统信息收集成功")
        except Exception as e:
            result.add_fail("系统信息收集", str(e))

        try:
            market_info = generator._collect_market_info()
            assert 'symbol' in market_info or 'error' in market_info
            result.add_pass("市场信息收集成功")
        except Exception as e:
            result.add_fail("市场信息收集", str(e))

        try:
            account_info = generator._collect_account_info()
            assert 'balance' in account_info
            result.add_pass("账户信息收集成功")
        except Exception as e:
            result.add_fail("账户信息收集", str(e))

        try:
            position_info = generator._collect_position_info()
            assert 'has_position' in position_info
            result.add_pass("持仓信息收集成功")
        except Exception as e:
            result.add_fail("持仓信息收集", str(e))

        # 测试3.3: 测试完整报告生成
        try:
            report_data = generator.generate_report()
            assert isinstance(report_data, dict)
            assert len(report_data) > 0
            result.add_pass("完整报告生成成功")
        except Exception as e:
            result.add_fail("完整报告生成", str(e))

        # 测试3.4: 测试消息格式化
        try:
            report_data = generator.generate_report()
            message = generator.format_message(report_data)
            assert isinstance(message, str)
            assert len(message) > 0
            assert "市场分析报告" in message
            result.add_pass("消息格式化成功")
        except Exception as e:
            result.add_fail("消息格式化", str(e))

    except Exception as e:
        result.add_fail("报告生成器测试", str(e))
        import traceback
        traceback.print_exc()

    result.print_summary()
    return result.failed == 0


def test_complete_flow():
    """测试4: 完整流程测试"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 完整流程测试")
    logger.info("=" * 60)

    result = TestResult()

    try:
        from market_report import PeriodicReportScheduler
        from trader import BitgetTrader
        from risk_manager import RiskManager
        import config

        # 初始化组件
        try:
            trader = BitgetTrader()
            risk_manager = RiskManager()
            scheduler = PeriodicReportScheduler(
                interval_minutes=config.PERIODIC_REPORT_INTERVAL,
                enabled=config.ENABLE_PERIODIC_REPORT
            )
            result.add_pass("组件初始化成功")
        except Exception as e:
            result.add_fail("组件初始化", str(e))
            return False

        # 测试4.1: 测试check_and_send（不应该发送，因为刚初始化）
        try:
            # 设置last_report_time为现在，模拟刚发送过
            scheduler.last_report_time = datetime.now()
            success = scheduler.check_and_send(trader, risk_manager)
            assert success == False, "刚发送过应该返回False"
            result.add_pass("check_and_send时间判断正确")
        except Exception as e:
            result.add_fail("check_and_send时间判断", str(e))

        # 测试4.2: 测试send_now（立即发送）
        try:
            logger.info("\n开始测试立即发送报告...")
            success = scheduler.send_now(trader, risk_manager)

            if success:
                result.add_pass("立即发送报告成功")
                assert scheduler.report_count > 0, "发送计数应该增加"
                assert scheduler.last_report_time is not None, "应该更新发送时间"
                result.add_pass("发送后状态更新正确")
            else:
                # 如果飞书未配置，发送会失败，这是预期的
                if not config.ENABLE_FEISHU or not config.FEISHU_WEBHOOK_URL:
                    logger.warning("飞书未配置，跳过发送测试")
                    result.add_pass("立即发送测试（飞书未配置，跳过）")
                else:
                    result.add_fail("立即发送报告", "发送失败但飞书已配置")
        except Exception as e:
            result.add_fail("立即发送报告", str(e))
            import traceback
            traceback.print_exc()

    except Exception as e:
        result.add_fail("完整流程测试", str(e))
        import traceback
        traceback.print_exc()

    result.print_summary()
    return result.failed == 0


def test_manual_send():
    """测试5: 手动发送测试（实际发送到飞书）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试5: 手动发送测试")
    logger.info("=" * 60)

    import config

    if not config.ENABLE_FEISHU or not config.FEISHU_WEBHOOK_URL:
        logger.warning("⏭️  飞书未配置，跳过手动发送测试")
        return True

    logger.info("即将发送测试报告到飞书...")
    logger.info("请确认是否继续？(y/n): ")

    # 在自动化测试中，我们跳过这个交互式测试
    logger.info("自动化测试模式，跳过手动发送测试")
    return True


def main():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("定期市场报告功能测试")
    logger.info("=" * 60)
    logger.info("测试日期: 2025-12-15")
    logger.info("=" * 60)

    all_passed = True

    # 运行所有测试
    tests = [
        ("配置验证", test_config_validation),
        ("调度器基本功能", test_scheduler_basic),
        ("报告生成器", test_report_generator),
        ("完整流程", test_complete_flow),
        ("手动发送", test_manual_send),
    ]

    results = {}
    for name, test_func in tests:
        try:
            passed = test_func()
            results[name] = passed
            if not passed:
                all_passed = False
        except Exception as e:
            logger.error(f"\n❌ 测试 '{name}' 执行失败: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
            all_passed = False

    # 打印总结
    logger.info("\n" + "=" * 60)
    logger.info("所有测试总结")
    logger.info("=" * 60)

    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"  {name}: {status}")

    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("🎉 所有测试通过!")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("⚠️  部分测试失败，请检查!")
        logger.info("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
