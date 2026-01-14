#!/usr/bin/env python3
"""
Policy Layer 测试脚本

测试内容：
1. Policy Layer 基本功能
2. PolicyDecision 创建和验证
3. 参数边界验证
4. TradingContext 构建
5. Claude Policy Analyzer 集成
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import get_logger
from ai.policy_layer import (
    PolicyLayer, PolicyDecision, TradingContext,
    MarketRegime, RiskMode, get_policy_layer
)

logger = get_logger("test_policy_layer")


class TestPolicyLayer:
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


def test_policy_layer_initialization():
    """测试1: Policy Layer 初始化"""
    policy = get_policy_layer()

    assert policy is not None, "Policy Layer 初始化失败"
    assert policy.current_params is not None, "PolicyParameters 未初始化"
    assert len(policy.param_bounds) > 0, "参数边界未设置"

    print(f"✓ Policy Layer 初始化成功")
    print(f"✓ 参数边界: {policy.param_bounds}")


def test_policy_parameters():
    """测试2: 策略参数获取"""
    policy = get_policy_layer()

    # 测试获取参数
    stop_loss = policy.get_stop_loss_percent()
    take_profit = policy.get_take_profit_percent()
    trailing_stop = policy.get_trailing_stop_percent()
    position_mult = policy.get_position_size_multiplier()
    risk_mode = policy.get_risk_mode()

    assert 0 < stop_loss < 1, f"止损百分比异常: {stop_loss}"
    assert 0 < take_profit < 1, f"止盈百分比异常: {take_profit}"
    assert 0 < trailing_stop < 1, f"移动止损百分比异常: {trailing_stop}"
    assert 0 < position_mult <= 2, f"仓位倍数异常: {position_mult}"
    assert isinstance(risk_mode, RiskMode), "风控模式类型错误"

    print(f"✓ 当前止损: {stop_loss:.2%}")
    print(f"✓ 当前止盈: {take_profit:.2%}")
    print(f"✓ 移动止损: {trailing_stop:.2%}")
    print(f"✓ 仓位倍数: {position_mult:.2f}x")
    print(f"✓ 风控模式: {risk_mode.value}")


def test_policy_decision_creation():
    """测试3: PolicyDecision 创建"""
    decision = PolicyDecision(
        regime=MarketRegime.TREND,
        regime_confidence=0.8,
        suggested_stop_loss_pct=0.025,
        suggested_take_profit_pct=0.05,
        suggested_trailing_stop_pct=0.015,
        enable_trailing_stop=True,
        suggested_position_multiplier=1.2,
        confidence=0.75,
        reason="测试决策：趋势市场，适度增加仓位",
        ttl_minutes=30
    )

    assert decision.regime == MarketRegime.TREND, "市场制度设置错误"
    assert decision.confidence == 0.75, "置信度设置错误"
    assert not decision.is_expired(), "决策不应该过期"

    print(f"✓ 决策制度: {decision.regime.value}")
    print(f"✓ 置信度: {decision.confidence:.2f}")
    print(f"✓ 止损建议: {decision.suggested_stop_loss_pct:.2%}")
    print(f"✓ 止盈建议: {decision.suggested_take_profit_pct:.2%}")
    print(f"✓ 仓位倍数: {decision.suggested_position_multiplier:.2f}x")
    print(f"✓ 原因: {decision.reason}")


def test_parameter_boundary_validation():
    """测试4: 参数边界验证"""
    policy = get_policy_layer()
    context = TradingContext()

    # 测试超出上限的止损
    decision = PolicyDecision(
        regime=MarketRegime.TREND,
        suggested_stop_loss_pct=0.10,  # 超出上限 (5%)
        confidence=0.8,
        reason="边界测试：超出上限"
    )

    success, reason, actions = policy.validate_and_apply_decision(decision, context)

    # 应该被限制在边界内
    actual_sl = policy.get_stop_loss_percent()
    assert actual_sl <= 0.05, f"止损未被限制在边界内: {actual_sl:.2%}"

    print(f"✓ 边界验证成功")
    print(f"✓ 建议值: 10.00% → 实际值: {actual_sl:.2%}")

    # 重置参数
    policy.force_reset()


def test_risk_mode_switching():
    """测试5: 风控模式切换"""
    policy = get_policy_layer()
    context = TradingContext()

    # 测试切换到防守模式
    decision = PolicyDecision(
        regime=MarketRegime.CHOP,
        suggested_risk_mode=RiskMode.DEFENSIVE,
        confidence=0.8,
        reason="测试：切换到防守模式"
    )

    success, reason, actions = policy.validate_and_apply_decision(decision, context)

    assert success, "风控模式切换失败"
    assert policy.get_risk_mode() == RiskMode.DEFENSIVE, "风控模式未正确切换"

    print(f"✓ 风控模式切换成功: {policy.get_risk_mode().value}")
    print(f"✓ 应用的动作: {[a.value for a in actions]}")

    # 重置参数
    policy.force_reset()


def test_trading_context():
    """测试6: TradingContext 创建"""
    context = TradingContext()

    # 设置测试数据
    context.recent_trades_count = 10
    context.win_rate = 0.6
    context.consecutive_losses = 2
    context.has_position = True
    context.position_side = "long"
    context.entry_price = 50000.0
    context.current_price = 51000.0
    context.unrealized_pnl = 100.0
    context.market_regime = MarketRegime.TREND
    context.current_risk_mode = RiskMode.NORMAL

    # 转换为字典
    context_dict = context.to_dict()

    assert context_dict['recent_trades_count'] == 10, "交易次数错误"
    assert context_dict['win_rate'] == 0.6, "胜率错误"
    assert context_dict['has_position'] == True, "持仓状态错误"
    assert context_dict['market_regime'] == 'trend', "市场制度错误"

    print(f"✓ TradingContext 创建成功")
    print(f"✓ 交易次数: {context.recent_trades_count}")
    print(f"✓ 胜率: {context.win_rate:.1%}")
    print(f"✓ 持仓: {context.has_position}")
    print(f"✓ 市场制度: {context.market_regime.value}")


def test_policy_status_report():
    """测试7: 状态报告"""
    policy = get_policy_layer()

    report = policy.get_status_report()

    assert 'current_parameters' in report, "状态报告缺少参数信息"
    assert 'last_update' in report, "状态报告缺少更新时间"

    print(f"✓ 状态报告生成成功")
    print(f"✓ 当前参数: {report['current_parameters']}")


def test_decision_expiration():
    """测试8: 决策过期机制"""
    from datetime import timedelta

    # 创建一个已过期的决策
    decision = PolicyDecision(
        regime=MarketRegime.TREND,
        confidence=0.8,
        reason="过期测试",
        ttl_minutes=0  # 立即过期
    )

    # 手动设置时间戳为过去
    decision.timestamp = datetime.now() - timedelta(minutes=1)

    assert decision.is_expired(), "决策应该已过期"

    print(f"✓ 决策过期机制正常")


def test_config_integration():
    """测试9: 配置集成"""
    # 检查配置是否正确加载
    assert hasattr(config, 'ENABLE_POLICY_LAYER'), "缺少 ENABLE_POLICY_LAYER 配置"
    assert hasattr(config, 'POLICY_UPDATE_INTERVAL'), "缺少 POLICY_UPDATE_INTERVAL 配置"
    assert hasattr(config, 'POLICY_LAYER_MODE'), "缺少 POLICY_LAYER_MODE 配置"

    print(f"✓ Policy Layer 配置已加载")
    print(f"✓ 启用状态: {config.ENABLE_POLICY_LAYER}")
    print(f"✓ 更新间隔: {config.POLICY_UPDATE_INTERVAL} 分钟")
    print(f"✓ 运行模式: {config.POLICY_LAYER_MODE}")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Policy Layer 测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestPolicyLayer()

    # 运行所有测试
    tester.run_test("Policy Layer 初始化", test_policy_layer_initialization)
    tester.run_test("策略参数获取", test_policy_parameters)
    tester.run_test("PolicyDecision 创建", test_policy_decision_creation)
    tester.run_test("参数边界验证", test_parameter_boundary_validation)
    tester.run_test("风控模式切换", test_risk_mode_switching)
    tester.run_test("TradingContext 创建", test_trading_context)
    tester.run_test("状态报告生成", test_policy_status_report)
    tester.run_test("决策过期机制", test_decision_expiration)
    tester.run_test("配置集成", test_config_integration)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
