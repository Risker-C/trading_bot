#!/usr/bin/env python3
"""
Claude API 调用优化功能测试脚本

测试内容：
1. 配置验证
2. 定时分析功能
3. 每日报告功能
4. 时区处理
5. API调用参数
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from utils.logger_utils import get_logger
from ai.claude_periodic_analyzer import get_claude_periodic_analyzer
import pandas as pd
import pytz

logger = get_logger("test_claude_optimization")


class TestClaudeOptimization:
    """测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.analyzer = None

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
    print("\n检查Claude API配置...")

    # 检查基础配置
    assert hasattr(config, 'ENABLE_CLAUDE_ANALYSIS'), "缺少 ENABLE_CLAUDE_ANALYSIS 配置"
    assert hasattr(config, 'CLAUDE_API_KEY'), "缺少 CLAUDE_API_KEY 配置"
    assert hasattr(config, 'CLAUDE_MODEL'), "缺少 CLAUDE_MODEL 配置"
    assert hasattr(config, 'CLAUDE_TIMEOUT'), "缺少 CLAUDE_TIMEOUT 配置"
    print("  ✓ 基础配置存在")

    # 检查定时分析配置
    assert hasattr(config, 'ENABLE_CLAUDE_PERIODIC_ANALYSIS'), "缺少 ENABLE_CLAUDE_PERIODIC_ANALYSIS 配置"
    assert hasattr(config, 'CLAUDE_PERIODIC_INTERVAL'), "缺少 CLAUDE_PERIODIC_INTERVAL 配置"
    assert hasattr(config, 'CLAUDE_ANALYZE_ON_STARTUP'), "缺少 CLAUDE_ANALYZE_ON_STARTUP 配置"
    print("  ✓ 定时分析配置存在")

    # 检查每日报告配置
    assert hasattr(config, 'ENABLE_CLAUDE_DAILY_REPORT'), "缺少 ENABLE_CLAUDE_DAILY_REPORT 配置"
    assert hasattr(config, 'CLAUDE_DAILY_REPORT_HOUR'), "缺少 CLAUDE_DAILY_REPORT_HOUR 配置"
    assert hasattr(config, 'CLAUDE_DAILY_REPORT_TIMEZONE'), "缺少 CLAUDE_DAILY_REPORT_TIMEZONE 配置"
    print("  ✓ 每日报告配置存在")

    # 验证配置值
    assert config.CLAUDE_ANALYZE_ON_STARTUP == False, "CLAUDE_ANALYZE_ON_STARTUP 应该为 False"
    print("  ✓ 启动时不立即分析配置正确")

    assert config.CLAUDE_PERIODIC_INTERVAL == 30, "CLAUDE_PERIODIC_INTERVAL 应该为 30"
    print("  ✓ 定时分析间隔配置正确（30分钟）")

    assert config.CLAUDE_DAILY_REPORT_HOUR == 8, "CLAUDE_DAILY_REPORT_HOUR 应该为 8"
    print("  ✓ 每日报告时间配置正确（8点）")

    assert config.CLAUDE_DAILY_REPORT_TIMEZONE == 'Asia/Shanghai', "时区应该为 Asia/Shanghai"
    print("  ✓ 时区配置正确（东八区）")


def test_analyzer_initialization():
    """测试2: 分析器初始化"""
    print("\n初始化Claude定时分析器...")

    analyzer = get_claude_periodic_analyzer()

    if not analyzer:
        print("  ⚠ Claude定时分析器未启用（可能是API配置问题）")
        return

    assert analyzer.enabled, "分析器应该被启用"
    print("  ✓ 分析器已启用")

    assert analyzer.interval_minutes == 30, "分析间隔应该为30分钟"
    print("  ✓ 分析间隔正确")

    assert analyzer.last_daily_report_date is None, "初始时每日报告日期应该为None"
    print("  ✓ 每日报告状态初始化正确")

    assert hasattr(analyzer, 'should_generate_daily_report'), "缺少 should_generate_daily_report 方法"
    print("  ✓ should_generate_daily_report 方法存在")

    assert hasattr(analyzer, 'generate_daily_report'), "缺少 generate_daily_report 方法"
    print("  ✓ generate_daily_report 方法存在")


def test_should_analyze_logic():
    """测试3: 定时分析判断逻辑"""
    print("\n测试定时分析判断逻辑...")

    analyzer = get_claude_periodic_analyzer()

    if not analyzer:
        print("  ⚠ 分析器未启用，跳过测试")
        return

    # 测试第一次分析（应该返回True）
    analyzer.last_analysis_time = None
    assert analyzer.should_analyze() == True, "首次应该返回True"
    print("  ✓ 首次分析判断正确")

    # 测试刚刚分析过（应该返回False）
    analyzer.last_analysis_time = datetime.now()
    assert analyzer.should_analyze() == False, "刚分析过应该返回False"
    print("  ✓ 刚分析过判断正确")

    # 测试超过间隔时间（应该返回True）
    analyzer.last_analysis_time = datetime.now() - timedelta(minutes=31)
    assert analyzer.should_analyze() == True, "超过间隔应该返回True"
    print("  ✓ 超过间隔判断正确")


def test_daily_report_timing():
    """测试4: 每日报告时间判断"""
    print("\n测试每日报告时间判断...")

    analyzer = get_claude_periodic_analyzer()

    if not analyzer:
        print("  ⚠ 分析器未启用，跳过测试")
        return

    # 获取配置的时区和报告时间
    tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(tz)
    report_hour = config.CLAUDE_DAILY_REPORT_HOUR

    print(f"  当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  报告时间: {report_hour}点")
    print(f"  当前小时: {now.hour}")

    # 测试今天已经生成过报告
    analyzer.last_daily_report_date = now.date()
    should_gen = analyzer.should_generate_daily_report()
    assert should_gen == False, "今天已生成过，应该返回False"
    print("  ✓ 今天已生成过报告判断正确")

    # 测试昨天生成的报告
    analyzer.last_daily_report_date = (now - timedelta(days=1)).date()

    if now.hour == report_hour and now.minute < 10:
        # 在时间窗口内（8:00-8:10）
        assert analyzer.should_generate_daily_report() == True, "在报告时间窗口内应该返回True"
        print("  ✓ 在报告时间窗口内判断正确")
    elif now.hour == report_hour:
        # 在报告小时内但超过10分钟（8:10-8:59）
        assert analyzer.should_generate_daily_report() == False, "超过时间窗口应该返回False"
        print("  ✓ 超过时间窗口判断正确")
    elif now.hour > report_hour:
        # 过了报告时间（修复后：不再无限重试）
        assert analyzer.should_generate_daily_report() == False, "过了报告时间窗口应该返回False"
        print("  ✓ 过了报告时间窗口判断正确（避免无限重试）")
    else:
        # 还没到报告时间
        assert analyzer.should_generate_daily_report() == False, "还没到报告时间应该返回False"
        print("  ✓ 还没到报告时间判断正确")


def test_timezone_handling():
    """测试5: 时区处理"""
    print("\n测试时区处理...")

    # 测试时区配置
    tz_name = config.CLAUDE_DAILY_REPORT_TIMEZONE
    tz = pytz.timezone(tz_name)
    print(f"  配置时区: {tz_name}")

    now_utc = datetime.now(pytz.UTC)
    now_local = now_utc.astimezone(tz)

    print(f"  UTC 时间: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  本地时间: {now_local.strftime('%Y-%m-%d %H:%M:%S')}")

    # 验证时区转换
    offset_hours = now_local.utcoffset().total_seconds() / 3600
    assert offset_hours == 8.0, "东八区应该是UTC+8"
    print("  ✓ 时区转换正确（UTC+8）")


def test_format_trade_history():
    """测试6: 交易历史格式化"""
    print("\n测试交易历史格式化...")

    analyzer = get_claude_periodic_analyzer()

    if not analyzer:
        print("  ⚠ 分析器未启用，跳过测试")
        return

    # 测试空交易历史
    empty_result = analyzer._format_trade_history([])
    assert "无交易记录" in empty_result, "空交易应该提示无交易记录"
    print("  ✓ 空交易历史处理正确")

    # 测试有交易历史
    test_trades = [
        {
            'side': 'long',
            'price': 50000.0,
            'amount': 0.01,
            'pnl': 100.0,
            'pnl_percent': 2.0,
            'strategy': 'test_strategy'
        },
        {
            'side': 'short',
            'price': 49000.0,
            'amount': 0.01,
            'pnl': -50.0,
            'pnl_percent': -1.0,
            'strategy': 'test_strategy'
        }
    ]

    result = analyzer._format_trade_history(test_trades)
    assert "共执行 2 笔交易" in result, "应该显示交易数量"
    assert "LONG" in result, "应该包含多单信息"
    assert "SHORT" in result, "应该包含空单信息"
    assert "总盈亏: $50.00" in result, "应该显示总盈亏"
    assert "胜率: 1/2" in result, "应该显示胜率"
    print("  ✓ 交易历史格式化正确")


def test_api_call_parameters():
    """测试7: API调用参数"""
    print("\n检查API调用参数...")

    analyzer = get_claude_periodic_analyzer()

    if not analyzer:
        print("  ⚠ 分析器未启用，跳过测试")
        return

    # 检查模型
    assert analyzer.model == config.CLAUDE_MODEL, "模型配置不匹配"
    print(f"  ✓ 模型: {analyzer.model}")

    # 检查超时
    assert analyzer.timeout == config.CLAUDE_TIMEOUT, "超时配置不匹配"
    print(f"  ✓ 超时: {analyzer.timeout}秒")

    # 检查推送配置
    assert analyzer.push_to_feishu == config.CLAUDE_PUSH_TO_FEISHU, "推送配置不匹配"
    print(f"  ✓ 飞书推送: {analyzer.push_to_feishu}")


def test_daily_report_prompt():
    """测试8: 每日报告提示词"""
    print("\n测试每日报告提示词...")

    analyzer = get_claude_periodic_analyzer()

    if not analyzer:
        print("  ⚠ 分析器未启用，跳过测试")
        return

    # 构建测试数据
    market_data = "测试市场数据"
    trade_review = "测试交易回顾"

    prompt = analyzer._build_daily_report_prompt(market_data, trade_review)

    # 验证提示词内容
    assert "昨日市场回顾" in prompt, "应该包含昨日市场回顾"
    assert "当前市场状态" in prompt, "应该包含当前市场状态"
    assert "今日行情预测" in prompt, "应该包含今日行情预测"
    assert "交易建议" in prompt, "应该包含交易建议"
    assert "风险因素" in prompt, "应该包含风险因素"
    assert "网络信息" in prompt, "应该包含网络信息要求"
    assert "JSON" in prompt, "应该要求JSON格式输出"
    print("  ✓ 提示词包含所有必要模块")

    assert market_data in prompt, "应该包含市场数据"
    assert trade_review in prompt, "应该包含交易回顾"
    print("  ✓ 提示词包含输入数据")


def test_scenario_summary():
    """测试9: 三种调用场景总结"""
    print("\n三种Claude调用场景总结:")
    print("-" * 60)

    print("\n场景1: 实时交易信号分析")
    print(f"  启用: {config.ENABLE_CLAUDE_ANALYSIS}")
    print(f"  触发: 量化机器人判断行情出现时")
    print(f"  频率: 由交易信号自然频率决定")
    print(f"  护栏: 日调用上限={config.CLAUDE_MAX_DAILY_CALLS}, 日成本上限=${config.CLAUDE_MAX_DAILY_COST}")

    print("\n场景2: 30分钟定时市场分析")
    print(f"  启用: {config.ENABLE_CLAUDE_PERIODIC_ANALYSIS}")
    print(f"  触发: 每{config.CLAUDE_PERIODIC_INTERVAL}分钟")
    print(f"  启动时分析: {config.CLAUDE_ANALYZE_ON_STARTUP}")
    print(f"  推送飞书: {config.CLAUDE_PUSH_TO_FEISHU}")

    print("\n场景3: 每日早上8点报告")
    print(f"  启用: {config.ENABLE_CLAUDE_DAILY_REPORT}")
    print(f"  触发: 每天{config.CLAUDE_DAILY_REPORT_HOUR}点 ({config.CLAUDE_DAILY_REPORT_TIMEZONE})")
    print(f"  包含交易回顾: {config.CLAUDE_DAILY_INCLUDE_TRADE_REVIEW}")
    print(f"  包含网络信息: {config.CLAUDE_DAILY_INCLUDE_WEB_SEARCH}")

    print("-" * 60)


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Claude API 调用优化功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestClaudeOptimization()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("分析器初始化", test_analyzer_initialization)
    tester.run_test("定时分析判断逻辑", test_should_analyze_logic)
    tester.run_test("每日报告时间判断", test_daily_report_timing)
    tester.run_test("时区处理", test_timezone_handling)
    tester.run_test("交易历史格式化", test_format_trade_history)
    tester.run_test("API调用参数", test_api_call_parameters)
    tester.run_test("每日报告提示词", test_daily_report_prompt)
    tester.run_test("三种调用场景总结", test_scenario_summary)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
