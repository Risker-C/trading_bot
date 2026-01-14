#!/usr/bin/env python3
"""
飞书推送智能过滤功能测试脚本

测试内容：
1. 配置项验证
2. 空闲推送过滤测试
3. 重复内容过滤测试
4. 非交易时段降频测试
5. 内容哈希计算测试
6. 相似度计算测试
7. 推送历史记录测试
8. 集成测试
"""

import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings as config
from monitoring.status_monitor import FeishuPushFilter
from utils.logger_utils import get_logger

logger = get_logger("test_feishu_push_filter")


class TestFeishuPushFilter:
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
    print("检查飞书推送过滤配置项...")

    # 检查必需的配置项
    assert hasattr(config, 'ENABLE_FEISHU_PUSH_FILTER'), "缺少 ENABLE_FEISHU_PUSH_FILTER 配置"
    assert hasattr(config, 'FEISHU_PRICE_CHANGE_THRESHOLD'), "缺少 FEISHU_PRICE_CHANGE_THRESHOLD 配置"
    assert hasattr(config, 'FEISHU_SKIP_IDLE_PUSH'), "缺少 FEISHU_SKIP_IDLE_PUSH 配置"
    assert hasattr(config, 'FEISHU_FILTER_DUPLICATE_CONTENT'), "缺少 FEISHU_FILTER_DUPLICATE_CONTENT 配置"
    assert hasattr(config, 'FEISHU_DUPLICATE_SIMILARITY_THRESHOLD'), "缺少 FEISHU_DUPLICATE_SIMILARITY_THRESHOLD 配置"
    assert hasattr(config, 'FEISHU_REDUCE_OFF_HOURS'), "缺少 FEISHU_REDUCE_OFF_HOURS 配置"
    assert hasattr(config, 'FEISHU_OFF_HOURS'), "缺少 FEISHU_OFF_HOURS 配置"
    assert hasattr(config, 'FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER'), "缺少 FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER 配置"

    # 检查配置值的合理性
    assert isinstance(config.ENABLE_FEISHU_PUSH_FILTER, bool), "ENABLE_FEISHU_PUSH_FILTER 必须是布尔值"
    assert 0 < config.FEISHU_PRICE_CHANGE_THRESHOLD < 1, "FEISHU_PRICE_CHANGE_THRESHOLD 必须在 0-1 之间"
    assert 0 < config.FEISHU_DUPLICATE_SIMILARITY_THRESHOLD <= 1, "FEISHU_DUPLICATE_SIMILARITY_THRESHOLD 必须在 0-1 之间"
    assert config.FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER >= 1, "FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER 必须 >= 1"

    print(f"✓ ENABLE_FEISHU_PUSH_FILTER = {config.ENABLE_FEISHU_PUSH_FILTER}")
    print(f"✓ FEISHU_PRICE_CHANGE_THRESHOLD = {config.FEISHU_PRICE_CHANGE_THRESHOLD}")
    print(f"✓ FEISHU_SKIP_IDLE_PUSH = {config.FEISHU_SKIP_IDLE_PUSH}")
    print(f"✓ FEISHU_FILTER_DUPLICATE_CONTENT = {config.FEISHU_FILTER_DUPLICATE_CONTENT}")
    print(f"✓ FEISHU_DUPLICATE_SIMILARITY_THRESHOLD = {config.FEISHU_DUPLICATE_SIMILARITY_THRESHOLD}")
    print(f"✓ FEISHU_REDUCE_OFF_HOURS = {config.FEISHU_REDUCE_OFF_HOURS}")
    print(f"✓ FEISHU_OFF_HOURS = {config.FEISHU_OFF_HOURS}")
    print(f"✓ FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER = {config.FEISHU_OFF_HOURS_INTERVAL_MULTIPLIER}")


def test_filter_initialization():
    """测试2: 过滤器初始化"""
    print("初始化飞书推送过滤器...")

    push_filter = FeishuPushFilter()

    assert push_filter is not None, "过滤器初始化失败"
    assert push_filter.enabled == config.ENABLE_FEISHU_PUSH_FILTER, "过滤器启用状态不正确"
    assert push_filter.last_push_content is None, "初始推送内容应为 None"
    assert push_filter.last_push_time is None, "初始推送时间应为 None"
    assert len(push_filter.push_history) == 0, "初始推送历史应为空"

    print(f"✓ 过滤器初始化成功")
    print(f"✓ 启用状态: {push_filter.enabled}")


def test_idle_push_filter():
    """测试3: 空闲推送过滤"""
    print("测试空闲推送过滤逻辑...")

    push_filter = FeishuPushFilter()

    # 测试场景1: 无持仓且行情变化小 - 应该过滤
    data1 = {
        'account_info': {'has_position': False},
        'market_change': {
            'available': True,
            'change_percent': 0.3  # 0.3% < 0.5%
        }
    }
    should_filter1, reason1 = push_filter._check_idle_push(data1)
    assert should_filter1 == True, "无持仓且行情变化小应该被过滤"
    print(f"✓ 场景1: 无持仓且行情变化小 - 已过滤 ({reason1})")

    # 测试场景2: 无持仓但行情变化大 - 不应该过滤
    data2 = {
        'account_info': {'has_position': False},
        'market_change': {
            'available': True,
            'change_percent': 0.8  # 0.8% > 0.5%
        }
    }
    should_filter2, reason2 = push_filter._check_idle_push(data2)
    assert should_filter2 == False, "无持仓但行情变化大不应该被过滤"
    print(f"✓ 场景2: 无持仓但行情变化大 - 未过滤")

    # 测试场景3: 有持仓 - 不应该过滤
    data3 = {
        'account_info': {'has_position': True},
        'market_change': {
            'available': True,
            'change_percent': 0.1  # 即使变化小
        }
    }
    should_filter3, reason3 = push_filter._check_idle_push(data3)
    assert should_filter3 == False, "有持仓不应该被过滤"
    print(f"✓ 场景3: 有持仓 - 未过滤")


def test_duplicate_content_filter():
    """测试4: 重复内容过滤"""
    print("测试重复内容过滤逻辑...")

    push_filter = FeishuPushFilter()

    message1 = """
🔔 系统状态推送
━━━━━━━━━━━━━━━
⚙️ 服务状态
时间: 2025-12-21 10:30:00
运行时长: 5小时30分钟
错误次数: 0
状态: ✅ 正常运行

📈 最近15分钟行情
当前价格: $42,500.00
价格变化: +150.00 (+0.35%) 📈
"""

    message2 = """
🔔 系统状态推送
━━━━━━━━━━━━━━━
⚙️ 服务状态
时间: 2025-12-21 10:45:00
运行时长: 5小时45分钟
错误次数: 0
状态: ✅ 正常运行

📈 最近15分钟行情
当前价格: $42,500.00
价格变化: +150.00 (+0.35%) 📈
"""

    message3 = """
🔔 系统状态推送
━━━━━━━━━━━━━━━
⚙️ 服务状态
时间: 2025-12-21 11:00:00
运行时长: 6小时
错误次数: 0
状态: ✅ 正常运行

📈 最近15分钟行情
当前价格: $43,000.00
价格变化: +500.00 (+1.18%) 📈
"""

    # 第一次推送 - 不应该过滤
    is_dup1, reason1 = push_filter._check_duplicate_content(message1)
    assert is_dup1 == False, "第一次推送不应该被过滤"
    print(f"✓ 第一次推送 - 未过滤")

    # 记录第一次推送
    push_filter.record_push(message1)

    # 第二次推送（内容高度相似）- 应该过滤
    is_dup2, reason2 = push_filter._check_duplicate_content(message2)
    assert is_dup2 == True, "高度相似的内容应该被过滤"
    print(f"✓ 第二次推送（高度相似）- 已过滤 ({reason2})")

    # 第三次推送（内容不同）- 不应该过滤
    is_dup3, reason3 = push_filter._check_duplicate_content(message3)
    assert is_dup3 == False, "内容不同不应该被过滤"
    print(f"✓ 第三次推送（内容不同）- 未过滤")


def test_off_hours_filter():
    """测试5: 非交易时段降频"""
    print("测试非交易时段降频逻辑...")

    push_filter = FeishuPushFilter()

    # 保存原始配置
    original_off_hours = push_filter.off_hours

    # 测试场景1: 当前时段在非活跃时段内
    current_hour = datetime.now().hour
    push_filter.off_hours = [current_hour]  # 设置当前时段为非活跃时段

    # 模拟刚推送过（5分钟前）
    push_filter.last_push_time = datetime.now() - timedelta(minutes=5)

    should_reduce1, reason1 = push_filter._check_off_hours()
    assert should_reduce1 == True, "非活跃时段且未达到降频间隔应该被过滤"
    print(f"✓ 场景1: 非活跃时段且未达到降频间隔 - 已过滤 ({reason1})")

    # 测试场景2: 当前时段在非活跃时段内，但已达到降频间隔
    push_filter.last_push_time = datetime.now() - timedelta(minutes=35)  # 35分钟前

    should_reduce2, reason2 = push_filter._check_off_hours()
    assert should_reduce2 == False, "非活跃时段但已达到降频间隔不应该被过滤"
    print(f"✓ 场景2: 非活跃时段但已达到降频间隔 - 未过滤")

    # 测试场景3: 当前时段不在非活跃时段内
    push_filter.off_hours = [(current_hour + 12) % 24]  # 设置为其他时段

    should_reduce3, reason3 = push_filter._check_off_hours()
    assert should_reduce3 == False, "活跃时段不应该被过滤"
    print(f"✓ 场景3: 活跃时段 - 未过滤")

    # 恢复原始配置
    push_filter.off_hours = original_off_hours


def test_content_hash():
    """测试6: 内容哈希计算"""
    print("测试内容哈希计算...")

    push_filter = FeishuPushFilter()

    message1 = """
价格: $42,500.00
变化: +150.00
时间: 2025-12-21 10:30:00
运行时长: 5小时30分钟
"""

    message2 = """
价格: $42,500.00
变化: +150.00
时间: 2025-12-21 10:45:00
运行时长: 5小时45分钟
"""

    message3 = """
价格: $43,000.00
变化: +500.00
时间: 2025-12-21 11:00:00
运行时长: 6小时
"""

    hash1 = push_filter._calculate_content_hash(message1)
    hash2 = push_filter._calculate_content_hash(message2)
    hash3 = push_filter._calculate_content_hash(message3)

    # message1 和 message2 移除时间后应该相同
    assert hash1 == hash2, "移除时间戳后的内容哈希应该相同"
    print(f"✓ 相同内容（不同时间）的哈希相同")

    # message3 内容不同，哈希应该不同
    assert hash1 != hash3, "不同内容的哈希应该不同"
    print(f"✓ 不同内容的哈希不同")


def test_similarity_calculation():
    """测试7: 相似度计算"""
    print("测试相似度计算...")

    push_filter = FeishuPushFilter()

    text1 = """
价格: $42,500.00
变化: +150.00 (+0.35%)
持仓: 无
状态: 正常
ADX: 25.5
波动率: 2.3%
"""

    text2 = """
价格: $42,500.00
变化: +150.00 (+0.35%)
持仓: 无
状态: 正常
ADX: 25.5
波动率: 2.3%
"""

    text3 = """
价格: $43,000.00
变化: +500.00 (+1.18%)
持仓: 有
状态: 正常
ADX: 35.2
波动率: 4.5%
"""

    similarity1 = push_filter._calculate_similarity(text1, text2)
    similarity2 = push_filter._calculate_similarity(text1, text3)

    assert similarity1 == 1.0, "完全相同的文本相似度应该为 1.0"
    print(f"✓ 完全相同的文本相似度: {similarity1:.2f}")

    assert similarity2 < 1.0, "不同的文本相似度应该小于 1.0"
    print(f"✓ 不同文本的相似度: {similarity2:.2f}")


def test_push_history():
    """测试8: 推送历史记录"""
    print("测试推送历史记录...")

    push_filter = FeishuPushFilter()

    # 记录多次推送
    for i in range(5):
        message = f"测试消息 {i}"
        push_filter.record_push(message)

    assert len(push_filter.push_history) == 5, "推送历史记录数量不正确"
    assert push_filter.last_push_content == "测试消息 4", "最后推送内容不正确"
    assert push_filter.last_push_time is not None, "最后推送时间应该被记录"

    print(f"✓ 推送历史记录数量: {len(push_filter.push_history)}")
    print(f"✓ 最后推送内容: {push_filter.last_push_content}")
    print(f"✓ 最后推送时间: {push_filter.last_push_time}")


def test_integrated_filter():
    """测试9: 集成过滤测试"""
    print("测试集成过滤逻辑...")

    push_filter = FeishuPushFilter()

    # 场景1: 无持仓且行情变化小 - 应该被过滤
    data1 = {
        'account_info': {'has_position': False},
        'market_change': {
            'available': True,
            'change_percent': 0.3
        }
    }
    message1 = "测试消息1"

    should_filter1, reason1 = push_filter.should_filter(data1, message1)
    assert should_filter1 == True, "场景1应该被过滤"
    print(f"✓ 场景1: 空闲推送 - 已过滤 ({reason1})")

    # 场景2: 有持仓但内容重复 - 应该被过滤
    data2 = {
        'account_info': {'has_position': True},
        'market_change': {
            'available': True,
            'change_percent': 0.8
        }
    }
    message2 = """
价格: $42,500.00
变化: +150.00
持仓: 有
"""

    # 先记录一次推送
    push_filter.record_push(message2)

    # 再次推送相同内容
    should_filter2, reason2 = push_filter.should_filter(data2, message2)
    assert should_filter2 == True, "场景2应该被过滤（重复内容）"
    print(f"✓ 场景2: 重复内容 - 已过滤 ({reason2})")

    # 场景3: 有持仓且内容不同 - 不应该被过滤
    # 注意：需要模拟足够长的时间间隔，避免触发非交易时段降频
    push_filter.last_push_time = datetime.now() - timedelta(minutes=35)  # 35分钟前

    data3 = {
        'account_info': {'has_position': True},
        'market_change': {
            'available': True,
            'change_percent': 1.5
        }
    }
    message3 = """
价格: $43,500.00
变化: +1000.00
持仓: 有
盈亏: +50 USDT
"""

    should_filter3, reason3 = push_filter.should_filter(data3, message3)
    assert should_filter3 == False, f"场景3不应该被过滤，但被过滤了: {reason3}"
    print(f"✓ 场景3: 有持仓且内容不同 - 未过滤")


def test_filter_disabled():
    """测试10: 过滤器禁用状态"""
    print("测试过滤器禁用状态...")

    # 临时禁用过滤器
    original_enabled = config.ENABLE_FEISHU_PUSH_FILTER
    config.ENABLE_FEISHU_PUSH_FILTER = False

    push_filter = FeishuPushFilter()

    data = {
        'account_info': {'has_position': False},
        'market_change': {
            'available': True,
            'change_percent': 0.1  # 很小的变化
        }
    }
    message = "测试消息"

    should_filter, reason = push_filter.should_filter(data, message)
    assert should_filter == False, "过滤器禁用时不应该过滤任何内容"
    print(f"✓ 过滤器禁用时不过滤任何内容")

    # 恢复配置
    config.ENABLE_FEISHU_PUSH_FILTER = original_enabled


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("飞书推送智能过滤功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestFeishuPushFilter()

    # 运行所有测试
    tester.run_test("配置项验证", test_config_validation)
    tester.run_test("过滤器初始化", test_filter_initialization)
    tester.run_test("空闲推送过滤", test_idle_push_filter)
    tester.run_test("重复内容过滤", test_duplicate_content_filter)
    tester.run_test("非交易时段降频", test_off_hours_filter)
    tester.run_test("内容哈希计算", test_content_hash)
    tester.run_test("相似度计算", test_similarity_calculation)
    tester.run_test("推送历史记录", test_push_history)
    tester.run_test("集成过滤测试", test_integrated_filter)
    tester.run_test("过滤器禁用状态", test_filter_disabled)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
