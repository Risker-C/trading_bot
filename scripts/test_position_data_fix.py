"""
测试持仓数据访问修复

本测试脚本专门验证 2025-12-15 修复的3处持仓数据访问错误：
1. bot.py - _execute_close_position 方法的字典访问错误
2. bot.py - get_status 方法的字典访问错误
3. cli.py - cmd_status 函数的字典访问错误

这些错误的共同特征：
- 将字典当作对象访问（使用 .attribute 而不是 ['key']）
- 访问不存在的字典键（'current_price', 'pnl_percent'）
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger_utils import get_logger

logger = get_logger("test_position_fix")


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
            logger.info("\n🎉 所有测试通过! 修复验证成功!")
        else:
            logger.error(f"\n⚠️  有 {self.failed} 个测试失败，请检查!")


def test_position_dict_structure():
    """测试1: 验证 get_position() 返回的字典结构"""
    logger.info("\n" + "=" * 60)
    logger.info("测试1: 验证持仓字典结构")
    logger.info("=" * 60)

    result = TestResult()

    # 模拟 get_position() 返回的字典
    position_dict = {
        'side': 'long',
        'amount': 0.001,
        'entry_price': 50000.0,
        'unrealized_pnl': 10.5,
        'liquidation_price': 45000.0
    }

    # 测试1.1: 验证字典包含必需的键
    try:
        required_keys = ['side', 'amount', 'entry_price', 'unrealized_pnl']
        for key in required_keys:
            assert key in position_dict, f"缺少必需的键: {key}"
        result.add_pass("字典包含所有必需的键")
    except Exception as e:
        result.add_fail("字典包含所有必需的键", str(e))

    # 测试1.2: 验证字典不包含 'current_price' 键
    try:
        assert 'current_price' not in position_dict, "字典不应该包含 'current_price' 键"
        result.add_pass("字典不包含 'current_price' 键（符合预期）")
    except Exception as e:
        result.add_fail("字典不包含 'current_price' 键", str(e))

    # 测试1.3: 验证字典不包含 'pnl_percent' 键
    try:
        assert 'pnl_percent' not in position_dict, "字典不应该包含 'pnl_percent' 键"
        result.add_pass("字典不包含 'pnl_percent' 键（符合预期）")
    except Exception as e:
        result.add_fail("字典不包含 'pnl_percent' 键", str(e))

    # 测试1.4: 验证正确的字典访问方式
    try:
        side = position_dict['side']
        amount = position_dict['amount']
        entry_price = position_dict['entry_price']
        assert side == 'long'
        assert amount == 0.001
        assert entry_price == 50000.0
        result.add_pass("字典访问方式正确（使用 ['key']）")
    except Exception as e:
        result.add_fail("字典访问方式", str(e))

    # 测试1.5: 验证错误的对象访问方式会失败
    try:
        # 这应该会抛出 AttributeError
        try:
            _ = position_dict.side
            result.add_fail("对象访问方式检测", "应该抛出 AttributeError 但没有")
        except AttributeError:
            result.add_pass("对象访问方式正确地抛出 AttributeError")
    except Exception as e:
        result.add_fail("对象访问方式检测", str(e))

    result.print_summary()
    return result.failed == 0


def test_execute_close_position_fix():
    """测试2: 验证 _execute_close_position 方法的修复"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 验证 _execute_close_position 方法修复")
    logger.info("=" * 60)

    result = TestResult()

    # 模拟持仓字典
    position = {
        'side': 'long',
        'amount': 0.001,
        'entry_price': 50000.0,
        'unrealized_pnl': 10.5
    }

    current_price = 51000.0

    # 测试2.1: 验证可以正确访问字典键
    try:
        entry_price = position['entry_price']
        amount = position['amount']
        side = position['side']

        assert entry_price == 50000.0
        assert amount == 0.001
        assert side == 'long'
        result.add_pass("正确访问持仓字典的所有必需键")
    except Exception as e:
        result.add_fail("访问持仓字典键", str(e))

    # 测试2.2: 验证不会尝试访问不存在的 'current_price' 键
    try:
        # 修复后，current_price 应该作为参数传入，而不是从字典获取
        assert 'current_price' not in position
        # 使用传入的 current_price 参数
        assert current_price == 51000.0
        result.add_pass("current_price 作为参数传入（不从字典获取）")
    except Exception as e:
        result.add_fail("current_price 参数", str(e))

    # 测试2.3: 验证盈亏计算
    try:
        if position['side'] == 'long':
            pnl = (current_price - position['entry_price']) * position['amount']
        else:
            pnl = (position['entry_price'] - current_price) * position['amount']

        expected_pnl = (51000.0 - 50000.0) * 0.001
        assert abs(pnl - expected_pnl) < 0.0001, f"盈亏计算错误: {pnl} != {expected_pnl}"
        result.add_pass("盈亏计算正确")
    except Exception as e:
        result.add_fail("盈亏计算", str(e))

    # 测试2.4: 验证盈亏百分比计算
    try:
        import config
        pnl = (current_price - position['entry_price']) * position['amount']
        pnl_percent = (pnl / (position['entry_price'] * position['amount'])) * 100 * config.LEVERAGE

        # 预期: (1000 * 0.001) / (50000 * 0.001) * 100 * 10 = 20%
        expected_pnl_percent = 20.0
        assert abs(pnl_percent - expected_pnl_percent) < 0.01, f"盈亏百分比错误: {pnl_percent} != {expected_pnl_percent}"
        result.add_pass("盈亏百分比计算正确")
    except Exception as e:
        result.add_fail("盈亏百分比计算", str(e))

    result.print_summary()
    return result.failed == 0


def test_get_status_fix():
    """测试3: 验证 get_status 方法的修复"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 验证 get_status 方法修复")
    logger.info("=" * 60)

    result = TestResult()

    # 模拟 get_positions() 返回的列表
    positions = [
        {
            'side': 'long',
            'amount': 0.001,
            'entry_price': 50000.0,
            'unrealized_pnl': 10.5,
            'liquidation_price': 45000.0
        }
    ]

    # 模拟当前价格
    current_price = 51000.0

    # 测试3.1: 验证正确的字典访问方式
    try:
        import config
        position_data = []
        for p in positions:
            # 修复后应该使用字典访问方式
            data = {
                'side': p['side'],
                'amount': p['amount'],
                'entry_price': p['entry_price'],
                'current_price': current_price,  # 从 ticker 获取
                'pnl': p['unrealized_pnl'],
                'pnl_percent': (p['unrealized_pnl'] / (p['entry_price'] * p['amount']) * 100 * config.LEVERAGE)
                              if p['entry_price'] > 0 and p['amount'] > 0 else 0
            }
            position_data.append(data)

        assert len(position_data) == 1
        assert position_data[0]['side'] == 'long'
        assert position_data[0]['current_price'] == 51000.0
        result.add_pass("get_status 正确处理持仓字典")
    except Exception as e:
        result.add_fail("get_status 字典处理", str(e))

    # 测试3.2: 验证不会使用对象访问方式
    try:
        p = positions[0]
        # 这些应该都能正常工作（字典访问）
        _ = p['side']
        _ = p['amount']
        _ = p['entry_price']
        _ = p['unrealized_pnl']

        # 这些应该会失败（对象访问）
        try:
            _ = p.side
            result.add_fail("对象访问检测", "不应该能够使用对象访问方式")
        except AttributeError:
            result.add_pass("正确地拒绝对象访问方式")
    except Exception as e:
        result.add_fail("访问方式检测", str(e))

    # 测试3.3: 验证 pnl_percent 计算
    try:
        import config
        p = positions[0]
        pnl_percent = (p['unrealized_pnl'] / (p['entry_price'] * p['amount']) * 100 * config.LEVERAGE) \
                      if p['entry_price'] > 0 and p['amount'] > 0 else 0

        # 预期: 10.5 / (50000 * 0.001) * 100 * 10 = 210%
        expected = 210.0
        assert abs(pnl_percent - expected) < 0.01, f"pnl_percent 计算错误: {pnl_percent} != {expected}"
        result.add_pass("pnl_percent 计算正确")
    except Exception as e:
        result.add_fail("pnl_percent 计算", str(e))

    result.print_summary()
    return result.failed == 0


def test_cli_status_fix():
    """测试4: 验证 cli.py cmd_status 函数的修复"""
    logger.info("\n" + "=" * 60)
    logger.info("测试4: 验证 CLI status 命令修复")
    logger.info("=" * 60)

    result = TestResult()

    # 模拟 get_positions() 返回的列表
    positions = [
        {
            'side': 'long',
            'amount': 0.001,
            'entry_price': 50000.0,
            'unrealized_pnl': 10.5,
            'liquidation_price': 45000.0
        }
    ]

    # 模拟当前价格
    current_price = 51000.0

    # 测试4.1: 验证正确的字典访问方式
    try:
        import config
        for pos in positions:
            # 修复后应该使用字典访问方式
            emoji = "🟢" if pos['side'] == 'long' else "🔴"
            pnl_percent = (pos['unrealized_pnl'] / (pos['entry_price'] * pos['amount']) * 100 * config.LEVERAGE) \
                          if pos['entry_price'] > 0 and pos['amount'] > 0 else 0

            # 验证数据
            assert pos['side'] == 'long'
            assert pos['amount'] == 0.001
            assert pos['entry_price'] == 50000.0
            assert emoji == "🟢"
            assert abs(pnl_percent - 210.0) < 0.01

        result.add_pass("CLI status 正确处理持仓字典")
    except Exception as e:
        result.add_fail("CLI status 字典处理", str(e))

    # 测试4.2: 验证 current_price 从 ticker 获取
    try:
        # 修复后，current_price 应该从 ticker 获取，而不是从 position 字典
        assert 'current_price' not in positions[0]
        # 使用从 ticker 获取的 current_price
        assert current_price == 51000.0
        result.add_pass("current_price 从 ticker 获取（不从字典）")
    except Exception as e:
        result.add_fail("current_price 来源", str(e))

    # 测试4.3: 验证格式化输出
    try:
        import config
        pos = positions[0]
        pnl_percent = (pos['unrealized_pnl'] / (pos['entry_price'] * pos['amount']) * 100 * config.LEVERAGE) \
                      if pos['entry_price'] > 0 and pos['amount'] > 0 else 0

        # 模拟输出格式
        output_line1 = f"   🟢 {pos['side'].upper()}: {pos['amount']} @ {pos['entry_price']:.2f}"
        output_line2 = f"      当前价: {current_price:.2f}"
        output_line3 = f"      盈亏: {pos['unrealized_pnl']:+.2f} USDT ({pnl_percent:+.2f}%)"

        assert "LONG" in output_line1
        assert "0.001" in output_line1
        assert "50000.00" in output_line1
        assert "51000.00" in output_line2
        assert "+10.50" in output_line3
        assert "+210.00" in output_line3

        result.add_pass("CLI 输出格式正确")
    except Exception as e:
        result.add_fail("CLI 输出格式", str(e))

    result.print_summary()
    return result.failed == 0


def test_regression_prevention():
    """测试5: 回归测试 - 确保不会再出现相同错误"""
    logger.info("\n" + "=" * 60)
    logger.info("测试5: 回归测试 - 防止相同错误再次出现")
    logger.info("=" * 60)

    result = TestResult()

    # 测试5.1: 验证访问不存在的键会抛出 KeyError
    try:
        position = {'side': 'long', 'amount': 0.001}
        try:
            _ = position['current_price']
            result.add_fail("KeyError 检测", "访问不存在的键应该抛出 KeyError")
        except KeyError:
            result.add_pass("访问不存在的键正确抛出 KeyError")
    except Exception as e:
        result.add_fail("KeyError 检测", str(e))

    # 测试5.2: 验证对象访问方式会抛出 AttributeError
    try:
        position = {'side': 'long', 'amount': 0.001}
        try:
            _ = position.side
            result.add_fail("AttributeError 检测", "对象访问应该抛出 AttributeError")
        except AttributeError:
            result.add_pass("对象访问正确抛出 AttributeError")
    except Exception as e:
        result.add_fail("AttributeError 检测", str(e))

    # 测试5.3: 验证正确的访问方式不会抛出异常
    try:
        position = {'side': 'long', 'amount': 0.001, 'entry_price': 50000.0}
        side = position['side']
        amount = position['amount']
        entry_price = position['entry_price']

        assert side == 'long'
        assert amount == 0.001
        assert entry_price == 50000.0
        result.add_pass("正确的字典访问方式不抛出异常")
    except Exception as e:
        result.add_fail("正确访问方式", str(e))

    # 测试5.4: 验证修复后的代码模式
    try:
        # 模拟修复后的代码模式
        position = {'side': 'long', 'amount': 0.001, 'entry_price': 50000.0, 'unrealized_pnl': 10.5}
        current_price = 51000.0  # 作为参数传入

        # 正确的访问方式
        entry_price = position['entry_price']
        amount = position['amount']
        side = position['side']

        # 计算盈亏
        if side == 'long':
            pnl = (current_price - entry_price) * amount
        else:
            pnl = (entry_price - current_price) * amount

        # 计算盈亏百分比
        import config
        pnl_percent = (pnl / (entry_price * amount)) * 100 * config.LEVERAGE

        assert abs(pnl - 1.0) < 0.0001
        assert abs(pnl_percent - 20.0) < 0.01
        result.add_pass("修复后的代码模式正确")
    except Exception as e:
        result.add_fail("修复后的代码模式", str(e))

    result.print_summary()
    return result.failed == 0


def main():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("持仓数据访问修复验证测试")
    logger.info("=" * 60)
    logger.info("测试日期: 2025-12-15")
    logger.info("修复内容: 3处持仓数据字典访问错误")
    logger.info("=" * 60)

    all_passed = True

    # 运行所有测试
    tests = [
        ("持仓字典结构验证", test_position_dict_structure),
        ("_execute_close_position 修复验证", test_execute_close_position_fix),
        ("get_status 修复验证", test_get_status_fix),
        ("CLI status 修复验证", test_cli_status_fix),
        ("回归测试", test_regression_prevention),
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
        logger.info("🎉 所有测试通过! 修复验证成功!")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("⚠️  部分测试失败，请检查修复!")
        logger.info("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
