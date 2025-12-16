#!/usr/bin/env python3
"""
Claude定时分析功能测试脚本

测试内容：
1. 配置验证
2. Claude定时分析器初始化
3. 市场数据格式化
4. 分析提示词构建
5. 飞书消息格式化
6. 完整分析流程（模拟）
7. 定时触发机制
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入必要的模块
import config
from logger_utils import get_logger
from claude_periodic_analyzer import ClaudePeriodicAnalyzer, get_claude_periodic_analyzer

logger = get_logger("test_claude_periodic_analysis")


class TestClaudePeriodicAnalysis:
    """测试类"""

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
    print("检查Claude定时分析配置...")

    # 检查基础配置
    assert hasattr(config, 'ENABLE_CLAUDE_PERIODIC_ANALYSIS'), "缺少 ENABLE_CLAUDE_PERIODIC_ANALYSIS 配置"
    assert hasattr(config, 'CLAUDE_PERIODIC_INTERVAL'), "缺少 CLAUDE_PERIODIC_INTERVAL 配置"
    assert hasattr(config, 'CLAUDE_ANALYSIS_DETAIL_LEVEL'), "缺少 CLAUDE_ANALYSIS_DETAIL_LEVEL 配置"
    assert hasattr(config, 'CLAUDE_ANALYZE_ON_STARTUP'), "缺少 CLAUDE_ANALYZE_ON_STARTUP 配置"
    assert hasattr(config, 'CLAUDE_PUSH_TO_FEISHU'), "缺少 CLAUDE_PUSH_TO_FEISHU 配置"
    assert hasattr(config, 'CLAUDE_ANALYSIS_MODULES'), "缺少 CLAUDE_ANALYSIS_MODULES 配置"

    print(f"  ENABLE_CLAUDE_PERIODIC_ANALYSIS: {config.ENABLE_CLAUDE_PERIODIC_ANALYSIS}")
    print(f"  CLAUDE_PERIODIC_INTERVAL: {config.CLAUDE_PERIODIC_INTERVAL} 分钟")
    print(f"  CLAUDE_ANALYSIS_DETAIL_LEVEL: {config.CLAUDE_ANALYSIS_DETAIL_LEVEL}")
    print(f"  CLAUDE_ANALYZE_ON_STARTUP: {config.CLAUDE_ANALYZE_ON_STARTUP}")
    print(f"  CLAUDE_PUSH_TO_FEISHU: {config.CLAUDE_PUSH_TO_FEISHU}")

    # 检查间隔范围
    assert 10 <= config.CLAUDE_PERIODIC_INTERVAL <= 360, \
        f"CLAUDE_PERIODIC_INTERVAL 必须在 10-360 之间，当前: {config.CLAUDE_PERIODIC_INTERVAL}"

    # 检查详细程度
    assert config.CLAUDE_ANALYSIS_DETAIL_LEVEL in ['simple', 'standard', 'detailed'], \
        f"CLAUDE_ANALYSIS_DETAIL_LEVEL 必须是 'simple', 'standard' 或 'detailed'，当前: {config.CLAUDE_ANALYSIS_DETAIL_LEVEL}"

    # 检查模块配置
    assert isinstance(config.CLAUDE_ANALYSIS_MODULES, dict), "CLAUDE_ANALYSIS_MODULES 必须是字典"
    print(f"  启用的分析模块: {[k for k, v in config.CLAUDE_ANALYSIS_MODULES.items() if v]}")

    # 检查依赖配置
    if config.ENABLE_CLAUDE_PERIODIC_ANALYSIS:
        assert config.ENABLE_CLAUDE_ANALYSIS, "启用Claude定时分析需要启用Claude分析"
        assert config.CLAUDE_API_KEY, "启用Claude定时分析需要配置Claude API Key"

        if config.CLAUDE_PUSH_TO_FEISHU:
            assert config.ENABLE_FEISHU, "启用飞书推送需要启用飞书通知"
            assert config.FEISHU_WEBHOOK_URL, "启用飞书推送需要配置飞书 Webhook URL"

    print("  所有配置验证通过")


def test_analyzer_initialization():
    """测试2: Claude定时分析器初始化"""
    print("测试Claude定时分析器初始化...")

    # 测试直接初始化
    analyzer = ClaudePeriodicAnalyzer(
        interval_minutes=30,
        enabled=True,
        detail_level='standard'
    )

    assert analyzer is not None, "分析器初始化失败"
    assert analyzer.interval_minutes == 30, "间隔设置错误"
    assert analyzer.detail_level == 'standard', "详细程度设置错误"
    assert analyzer.last_analysis_time is None, "初始分析时间应为None"
    assert analyzer.analysis_count == 0, "初始分析次数应为0"

    print(f"  分析器初始化成功")
    print(f"  间隔: {analyzer.interval_minutes} 分钟")
    print(f"  详细程度: {analyzer.detail_level}")
    print(f"  启用状态: {analyzer.enabled}")

    # 测试单例获取
    singleton_analyzer = get_claude_periodic_analyzer()
    if config.ENABLE_CLAUDE_PERIODIC_ANALYSIS:
        assert singleton_analyzer is not None, "单例获取失败"
        print(f"  单例获取成功")
    else:
        assert singleton_analyzer is None, "配置未启用时应返回None"
        print(f"  配置未启用，单例返回None（正确）")


def test_market_data_formatting():
    """测试3: 市场数据格式化"""
    print("测试市场数据格式化...")

    # 创建模拟K线数据
    df = create_mock_kline_data()

    # 创建模拟技术指标
    indicators = {
        'rsi': 55.5,
        'macd': 100.5,
        'macd_signal': 95.3,
        'macd_histogram': 5.2,
        'ema_short': 42500.0,
        'ema_long': 42300.0,
        'bb_upper': 43000.0,
        'bb_middle': 42500.0,
        'bb_lower': 42000.0,
        'bb_percent_b': 0.5,
        'adx': 28.5,
        'plus_di': 25.0,
        'minus_di': 20.0,
        'volume_ratio': 1.2,
        'atr': 150.0
    }

    current_price = 42500.0

    # 创建分析器
    analyzer = ClaudePeriodicAnalyzer(interval_minutes=30, enabled=True)

    # 测试无持仓情况
    market_data = analyzer._format_market_data(df, current_price, indicators, None)

    assert market_data is not None, "市场数据格式化失败"
    assert isinstance(market_data, str), "市场数据应为字符串"
    assert "市场数据" in market_data, "缺少市场数据标题"
    assert "价格信息" in market_data, "缺少价格信息"
    assert "技术指标" in market_data, "缺少技术指标"
    assert "当前持仓" in market_data, "缺少持仓信息"
    assert "无持仓" in market_data, "应显示无持仓"

    print(f"  无持仓数据格式化成功")
    print(f"  数据长度: {len(market_data)} 字符")

    # 测试有持仓情况
    position_info = {
        'side': 'long',
        'amount': 0.1,
        'entry_price': 42000.0,
        'unrealized_pnl': 50.0,
        'pnl_percent': 1.19
    }

    market_data_with_pos = analyzer._format_market_data(df, current_price, indicators, position_info)

    assert "方向: long" in market_data_with_pos, "缺少持仓方向"
    assert "数量: 0.1" in market_data_with_pos, "缺少持仓数量"
    assert "入场价: 42000.0" in market_data_with_pos, "缺少入场价"

    print(f"  有持仓数据格式化成功")


def test_analysis_prompt_building():
    """测试4: 分析提示词构建"""
    print("测试分析提示词构建...")

    analyzer = ClaudePeriodicAnalyzer(interval_minutes=30, enabled=True, detail_level='standard')

    # 创建模拟市场数据
    market_data = "模拟市场数据..."

    # 测试无持仓提示词
    prompt = analyzer._build_analysis_prompt(market_data, has_position=False)

    assert prompt is not None, "提示词构建失败"
    assert isinstance(prompt, str), "提示词应为字符串"
    assert "市场趋势分析" in prompt, "缺少趋势分析要求"
    assert "风险评估" in prompt, "缺少风险评估要求"
    assert "入场机会" in prompt, "缺少入场机会要求"
    assert "开仓建议" in prompt, "无持仓时应包含开仓建议"
    assert "JSON" in prompt, "缺少JSON格式要求"

    print(f"  无持仓提示词构建成功")
    print(f"  提示词长度: {len(prompt)} 字符")

    # 测试有持仓提示词
    prompt_with_pos = analyzer._build_analysis_prompt(market_data, has_position=True)

    assert "持仓建议" in prompt_with_pos, "有持仓时应包含持仓建议"

    print(f"  有持仓提示词构建成功")

    # 测试不同详细程度
    for level in ['simple', 'standard', 'detailed']:
        analyzer_level = ClaudePeriodicAnalyzer(interval_minutes=30, enabled=True, detail_level=level)
        prompt_level = analyzer_level._build_analysis_prompt(market_data, has_position=False)
        assert prompt_level is not None, f"{level} 级别提示词构建失败"
        print(f"  {level} 级别提示词构建成功")


def test_feishu_message_formatting():
    """测试5: 飞书消息格式化"""
    print("测试飞书消息格式化...")

    analyzer = ClaudePeriodicAnalyzer(interval_minutes=30, enabled=True)

    # 创建模拟分析结果
    analysis = {
        'timestamp': '2025-12-16 10:30:00',
        'current_price': 42500.0,
        'analysis_count': 1,
        'market_trend': {
            'direction': '上涨',
            'strength': '强',
            'sustainability': '高',
            'summary': '当前市场处于强势上涨趋势中'
        },
        'risk_assessment': {
            'risk_level': '低',
            'risk_factors': ['无明显风险'],
            'summary': '市场风险较低，技术指标健康'
        },
        'entry_opportunities': {
            'has_opportunity': True,
            'direction': '做多',
            'entry_price': 42400.0,
            'confidence': 0.75,
            'summary': '存在较好的做多机会'
        },
        'position_advice': {
            'action': '持有',
            'reason': '趋势向上',
            'position_size': '10%',
            'summary': '建议继续持有当前仓位'
        },
        'market_sentiment': {
            'sentiment': '中性',
            'impact': '情绪平稳',
            'summary': '市场情绪相对平稳'
        },
        'overall_summary': '市场处于健康的上涨趋势中，建议保持当前策略',
        'key_points': [
            'EMA9 > EMA21，趋势向上',
            'RSI 处于健康区间',
            '成交量配合良好'
        ]
    }

    # 格式化消息
    message = analyzer._format_feishu_message(analysis)

    assert message is not None, "飞书消息格式化失败"
    assert isinstance(message, str), "飞书消息应为字符串"
    assert "Claude AI 市场分析报告" in message, "缺少标题"
    assert "市场趋势" in message, "缺少趋势分析"
    assert "风险评估" in message, "缺少风险评估"
    assert "入场机会" in message, "缺少入场机会"
    assert "持仓建议" in message, "缺少持仓建议"
    assert "市场情绪" in message, "缺少市场情绪"
    assert "整体总结" in message, "缺少整体总结"
    assert "关键点" in message, "缺少关键点"
    assert "📊" in message or "📈" in message or "📉" in message, "缺少emoji"

    print(f"  飞书消息格式化成功")
    print(f"  消息长度: {len(message)} 字符")
    print(f"\n预览消息（前500字符）:")
    print(f"{'-'*60}")
    print(message[:500])
    print(f"{'-'*60}")


def test_timing_mechanism():
    """测试6: 定时触发机制"""
    print("测试定时触发机制...")

    # 创建分析器，间隔1分钟
    analyzer = ClaudePeriodicAnalyzer(interval_minutes=1, enabled=True)

    # 初始状态应该触发
    assert analyzer.should_analyze() == True, "初始状态应该触发分析"
    print(f"  初始状态检查通过")

    # 设置上次分析时间为现在
    analyzer.last_analysis_time = datetime.now()

    # 立即检查不应该触发
    assert analyzer.should_analyze() == False, "刚分析完不应该立即触发"
    print(f"  间隔检查通过")

    # 设置上次分析时间为2分钟前
    analyzer.last_analysis_time = datetime.now() - timedelta(minutes=2)

    # 应该触发
    assert analyzer.should_analyze() == True, "超过间隔应该触发"
    print(f"  超时触发检查通过")

    # 测试禁用状态
    analyzer.enabled = False
    assert analyzer.should_analyze() == False, "禁用状态不应该触发"
    print(f"  禁用状态检查通过")


def test_json_parsing():
    """测试7: JSON响应解析"""
    print("测试JSON响应解析...")

    analyzer = ClaudePeriodicAnalyzer(interval_minutes=30, enabled=True)

    # 测试直接JSON
    json_text = '{"test": "value", "number": 123}'
    result = analyzer._parse_response(json_text)
    assert result is not None, "直接JSON解析失败"
    assert result['test'] == 'value', "JSON值解析错误"
    print(f"  直接JSON解析成功")

    # 测试JSON代码块
    json_with_block = '''```json
{
  "test": "value",
  "number": 123
}
```'''
    result = analyzer._parse_response(json_with_block)
    assert result is not None, "JSON代码块解析失败"
    assert result['test'] == 'value', "JSON代码块值解析错误"
    print(f"  JSON代码块解析成功")

    # 测试混合文本
    mixed_text = '''这是一些文本
{
  "test": "value",
  "number": 123
}
还有一些文本'''
    result = analyzer._parse_response(mixed_text)
    assert result is not None, "混合文本JSON解析失败"
    assert result['test'] == 'value', "混合文本JSON值解析错误"
    print(f"  混合文本JSON解析成功")

    # 测试无效JSON
    invalid_json = "这不是JSON"
    result = analyzer._parse_response(invalid_json)
    assert result is None, "无效JSON应返回None"
    print(f"  无效JSON处理正确")


def create_mock_kline_data():
    """创建模拟K线数据"""
    dates = pd.date_range(end=datetime.now(), periods=200, freq='15min')

    # 生成模拟价格数据
    base_price = 42000
    prices = base_price + np.cumsum(np.random.randn(200) * 50)

    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(200) * 10,
        'high': prices + np.abs(np.random.randn(200) * 20),
        'low': prices - np.abs(np.random.randn(200) * 20),
        'close': prices,
        'volume': np.random.randint(100, 1000, 200)
    })

    return df


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Claude定时分析功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestClaudePeriodicAnalysis()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("Claude定时分析器初始化", test_analyzer_initialization)
    tester.run_test("市场数据格式化", test_market_data_formatting)
    tester.run_test("分析提示词构建", test_analysis_prompt_building)
    tester.run_test("飞书消息格式化", test_feishu_message_formatting)
    tester.run_test("定时触发机制", test_timing_mechanism)
    tester.run_test("JSON响应解析", test_json_parsing)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
