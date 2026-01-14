#!/usr/bin/env python3
"""
测试脚本：持仓历史价格持久化功能
测试重启后历史最高价/最低价是否正确恢复

测试场景：
1. 数据库迁移验证
2. 持仓保存功能测试
3. 持仓恢复功能测试
4. 模拟重启场景测试
5. 历史价格一致性验证
"""

import sys
import os
import sqlite3
from datetime import datetime
from typing import Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import db, get_logger
from risk.risk_manager import RiskManager, PositionInfo

logger = get_logger("test_position_history")

# 测试配置
TEST_DB_PATH = "/root/trading_bot/trading_bot.db"
TEST_SYMBOL = "BTCUSDT"


class TestPositionHistoryPersistence:
    """持仓历史价格持久化测试类"""

    def __init__(self):
        self.test_results = []
        self.risk_manager = RiskManager()

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"{status} | {test_name}")
        if message:
            print(f"      {message}")

    def test_database_schema(self) -> bool:
        """测试1: 验证数据库表结构"""
        print("\n" + "=" * 60)
        print("测试1: 数据库表结构验证")
        print("=" * 60)

        try:
            conn = sqlite3.connect(TEST_DB_PATH)
            cursor = conn.cursor()

            # 检查position_snapshots表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='position_snapshots'
            """)
            table_exists = cursor.fetchone() is not None

            if not table_exists:
                self.log_test("表存在性检查", False, "position_snapshots表不存在")
                conn.close()
                return False

            self.log_test("表存在性检查", True, "position_snapshots表存在")

            # 检查必需字段
            cursor.execute("PRAGMA table_info(position_snapshots)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}

            required_fields = {
                'highest_price': 'REAL',
                'lowest_price': 'REAL',
                'entry_time': 'TIMESTAMP'
            }

            all_fields_exist = True
            for field, field_type in required_fields.items():
                if field in columns:
                    self.log_test(f"字段检查: {field}", True, f"类型: {columns[field]}")
                else:
                    self.log_test(f"字段检查: {field}", False, "字段不存在")
                    all_fields_exist = False

            conn.close()
            return all_fields_exist

        except Exception as e:
            self.log_test("数据库连接", False, f"错误: {e}")
            return False

    def test_position_save(self) -> bool:
        """测试2: 持仓保存功能"""
        print("\n" + "=" * 60)
        print("测试2: 持仓保存功能")
        print("=" * 60)

        try:
            # 创建测试持仓
            test_entry_price = 90000.0
            test_highest_price = 91000.0
            test_lowest_price = 89500.0

            self.risk_manager.set_position(
                side='long',
                amount=0.001,
                entry_price=test_entry_price,
                highest_price=test_highest_price,
                lowest_price=test_lowest_price,
                entry_time=datetime.now()
            )

            self.log_test("创建测试持仓", True, f"开仓价: {test_entry_price}")

            # 验证内存中的持仓
            if self.risk_manager.position:
                self.log_test("内存持仓验证", True,
                             f"highest={self.risk_manager.position.highest_price:.2f}, "
                             f"lowest={self.risk_manager.position.lowest_price:.2f}")
            else:
                self.log_test("内存持仓验证", False, "持仓对象为None")
                return False

            # 保存到数据库
            self.risk_manager._save_position_to_db()
            self.log_test("保存到数据库", True, "调用_save_position_to_db()")

            # 从数据库读取验证
            snapshot = db.get_latest_position_snapshot(TEST_SYMBOL)

            if snapshot:
                db_highest = snapshot['highest_price']
                db_lowest = snapshot['lowest_price']

                highest_match = abs(db_highest - test_highest_price) < 0.01
                lowest_match = abs(db_lowest - test_lowest_price) < 0.01

                self.log_test("数据库读取验证", True,
                             f"highest={db_highest:.2f}, lowest={db_lowest:.2f}")
                self.log_test("最高价一致性", highest_match,
                             f"预期: {test_highest_price:.2f}, 实际: {db_highest:.2f}")
                self.log_test("最低价一致性", lowest_match,
                             f"预期: {test_lowest_price:.2f}, 实际: {db_lowest:.2f}")

                return highest_match and lowest_match
            else:
                self.log_test("数据库读取验证", False, "未找到快照记录")
                return False

        except Exception as e:
            self.log_test("持仓保存测试", False, f"错误: {e}")
            return False
        finally:
            # 清理测试持仓
            self.risk_manager.clear_position()

    def test_position_restore(self) -> bool:
        """测试3: 持仓恢复功能"""
        print("\n" + "=" * 60)
        print("测试3: 持仓恢复功能")
        print("=" * 60)

        try:
            # 先保存一个测试持仓
            test_entry_price = 92000.0
            test_highest_price = 93500.0
            test_lowest_price = 91200.0

            self.risk_manager.set_position(
                side='short',
                amount=0.002,
                entry_price=test_entry_price,
                highest_price=test_highest_price,
                lowest_price=test_lowest_price,
                entry_time=datetime.now()
            )
            self.risk_manager._save_position_to_db()

            self.log_test("准备测试数据", True,
                         f"保存持仓: highest={test_highest_price:.2f}, lowest={test_lowest_price:.2f}")

            # 清除内存中的持仓（模拟重启）
            self.risk_manager.clear_position()
            self.log_test("清除内存持仓", True, "模拟重启场景")

            # 从数据库恢复
            snapshot = db.get_latest_position_snapshot(TEST_SYMBOL)

            if not snapshot:
                self.log_test("读取数据库快照", False, "未找到快照")
                return False

            self.log_test("读取数据库快照", True, f"找到快照: {snapshot['side']} @ {snapshot['entry_price']:.2f}")

            # 使用恢复的数据创建新持仓
            self.risk_manager.set_position(
                side=snapshot['side'],
                amount=0.002,
                entry_price=snapshot['entry_price'],
                highest_price=snapshot['highest_price'],
                lowest_price=snapshot['lowest_price'],
                entry_time=datetime.now()
            )

            # 验证恢复的数据
            restored_highest = self.risk_manager.position.highest_price
            restored_lowest = self.risk_manager.position.lowest_price

            highest_match = abs(restored_highest - test_highest_price) < 0.01
            lowest_match = abs(restored_lowest - test_lowest_price) < 0.01

            self.log_test("恢复最高价", highest_match,
                         f"预期: {test_highest_price:.2f}, 实际: {restored_highest:.2f}")
            self.log_test("恢复最低价", lowest_match,
                         f"预期: {test_lowest_price:.2f}, 实际: {restored_lowest:.2f}")

            return highest_match and lowest_match

        except Exception as e:
            self.log_test("持仓恢复测试", False, f"错误: {e}")
            return False
        finally:
            self.risk_manager.clear_position()

    def test_price_update_persistence(self) -> bool:
        """测试4: 价格更新持久化"""
        print("\n" + "=" * 60)
        print("测试4: 价格更新持久化")
        print("=" * 60)

        try:
            # 创建初始持仓
            initial_price = 88000.0
            self.risk_manager.set_position(
                side='long',
                amount=0.001,
                entry_price=initial_price,
                entry_time=datetime.now()
            )

            self.log_test("创建初始持仓", True, f"开仓价: {initial_price:.2f}")

            # 模拟价格上涨
            new_high_price = 89500.0
            self.risk_manager.position.update_price(new_high_price)
            self.risk_manager._save_position_to_db()

            self.log_test("更新价格(上涨)", True, f"新价格: {new_high_price:.2f}")

            # 验证最高价更新
            snapshot1 = db.get_latest_position_snapshot(TEST_SYMBOL)
            highest_updated = abs(snapshot1['highest_price'] - new_high_price) < 0.01

            self.log_test("最高价更新验证", highest_updated,
                         f"数据库中的最高价: {snapshot1['highest_price']:.2f}")

            # 模拟价格下跌
            new_low_price = 87200.0
            self.risk_manager.position.update_price(new_low_price)
            self.risk_manager._save_position_to_db()

            self.log_test("更新价格(下跌)", True, f"新价格: {new_low_price:.2f}")

            # 验证最低价更新
            snapshot2 = db.get_latest_position_snapshot(TEST_SYMBOL)
            lowest_updated = abs(snapshot2['lowest_price'] - new_low_price) < 0.01

            self.log_test("最低价更新验证", lowest_updated,
                         f"数据库中的最低价: {snapshot2['lowest_price']:.2f}")

            return highest_updated and lowest_updated

        except Exception as e:
            self.log_test("价格更新测试", False, f"错误: {e}")
            return False
        finally:
            self.risk_manager.clear_position()

    def test_trailing_stop_calculation(self) -> bool:
        """测试5: 移动止损计算验证"""
        print("\n" + "=" * 60)
        print("测试5: 移动止损计算验证")
        print("=" * 60)

        try:
            # 创建持仓并设置历史最高价
            entry_price = 90000.0
            highest_price = 91500.0  # 涨幅 1.67%

            self.risk_manager.set_position(
                side='long',
                amount=0.001,
                entry_price=entry_price,
                highest_price=highest_price,
                lowest_price=entry_price,
                entry_time=datetime.now()
            )

            self.log_test("创建测试持仓", True,
                         f"开仓价: {entry_price:.2f}, 最高价: {highest_price:.2f}")

            # 计算移动止损价
            trailing_stop = self.risk_manager.calculate_trailing_stop(
                current_price=91000.0,
                position=self.risk_manager.position
            )

            expected_trailing = highest_price * (1 - config.TRAILING_STOP_PERCENT)
            should_enable = expected_trailing > entry_price

            self.log_test("移动止损计算", True,
                         f"止损价: {trailing_stop:.2f}, 预期: {expected_trailing:.2f}")
            self.log_test("移动止损启用条件", should_enable,
                         f"止损价({trailing_stop:.2f}) > 开仓价({entry_price:.2f}): {should_enable}")

            # 验证计算正确性
            calculation_correct = abs(trailing_stop - expected_trailing) < 0.01 if trailing_stop > 0 else not should_enable

            self.log_test("计算正确性验证", calculation_correct,
                         f"计算结果与预期{'一致' if calculation_correct else '不一致'}")

            return calculation_correct

        except Exception as e:
            self.log_test("移动止损计算测试", False, f"错误: {e}")
            return False
        finally:
            self.risk_manager.clear_position()

    def test_snapshot_matching(self) -> bool:
        """测试6: 快照匹配逻辑"""
        print("\n" + "=" * 60)
        print("测试6: 快照匹配逻辑")
        print("=" * 60)

        try:
            # 保存一个测试快照
            test_side = 'long'
            test_entry = 89000.0
            test_highest = 89800.0
            test_lowest = 88500.0

            self.risk_manager.set_position(
                side=test_side,
                amount=0.001,
                entry_price=test_entry,
                highest_price=test_highest,
                lowest_price=test_lowest,
                entry_time=datetime.now()
            )
            self.risk_manager._save_position_to_db()
            self.risk_manager.clear_position()

            self.log_test("准备测试快照", True, f"{test_side} @ {test_entry:.2f}")

            # 测试匹配场景
            snapshot = db.get_latest_position_snapshot(TEST_SYMBOL)

            # 场景1: 完全匹配
            match1 = (snapshot['side'] == test_side and
                     abs(snapshot['entry_price'] - test_entry) < 1.0)
            self.log_test("场景1: 完全匹配", match1,
                         f"方向和价格都匹配")

            # 场景2: 方向不匹配
            match2 = (snapshot['side'] == 'short' and
                     abs(snapshot['entry_price'] - test_entry) < 1.0)
            self.log_test("场景2: 方向不匹配", not match2,
                         f"应该不匹配（预期结果）")

            # 场景3: 价格差异过大
            match3 = (snapshot['side'] == test_side and
                     abs(snapshot['entry_price'] - (test_entry + 10.0)) < 1.0)
            self.log_test("场景3: 价格差异过大", not match3,
                         f"应该不匹配（预期结果）")

            return match1 and not match2 and not match3

        except Exception as e:
            self.log_test("快照匹配测试", False, f"错误: {e}")
            return False
        finally:
            self.risk_manager.clear_position()

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("持仓历史价格持久化功能测试")
        print("=" * 60)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"数据库路径: {TEST_DB_PATH}")
        print(f"测试交易对: {TEST_SYMBOL}")

        # 运行所有测试
        tests = [
            self.test_database_schema,
            self.test_position_save,
            self.test_position_restore,
            self.test_price_update_persistence,
            self.test_trailing_stop_calculation,
            self.test_snapshot_matching,
        ]

        for test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"\n❌ 测试执行异常: {test_func.__name__}")
                print(f"   错误: {e}")

        # 生成测试报告
        self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        print("\n" + "=" * 60)
        print("测试报告")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['passed'])
        failed_tests = total_tests - passed_tests

        print(f"\n总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"通过率: {(passed_tests/total_tests*100):.1f}%")

        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  ❌ {result['test']}")
                    if result['message']:
                        print(f"     {result['message']}")

        print("\n" + "=" * 60)
        if failed_tests == 0:
            print("✅ 所有测试通过！")
        else:
            print(f"⚠️  有 {failed_tests} 个测试失败，请检查")
        print("=" * 60)

        # 保存测试报告到文件
        report_file = f"/root/trading_bot/logs/test_position_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("持仓历史价格持久化功能测试报告\n")
                f.write("=" * 60 + "\n")
                f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"总测试数: {total_tests}\n")
                f.write(f"通过: {passed_tests}\n")
                f.write(f"失败: {failed_tests}\n")
                f.write(f"通过率: {(passed_tests/total_tests*100):.1f}%\n\n")

                for result in self.test_results:
                    status = "PASS" if result['passed'] else "FAIL"
                    f.write(f"[{status}] {result['test']}\n")
                    if result['message']:
                        f.write(f"      {result['message']}\n")

            print(f"\n📄 测试报告已保存: {report_file}")
        except Exception as e:
            print(f"\n⚠️  保存测试报告失败: {e}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("开始测试持仓历史价格持久化功能")
    print("=" * 60)

    tester = TestPositionHistoryPersistence()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
