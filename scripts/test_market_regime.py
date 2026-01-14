"""
市场状态检测测试用例
测试优化后的市场状态判断逻辑
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader import BitgetTrader
from market_regime import MarketRegimeDetector, MarketRegime
import config
from utils.logger_utils import get_logger

logger = get_logger("test_market_regime")


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'=' * 20} {title} {'=' * 20}")
    else:
        print("=" * 60)


def test_current_market():
    """测试当前市场状态"""
    print_separator("测试当前市场状态")

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        print("❌ 获取K线数据失败")
        return

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    print(f"\n当前市场状态: {regime_info.regime.value.upper()}")
    print(f"置信度: {regime_info.confidence:.0%}")
    print(f"ADX: {regime_info.adx:.1f}")
    print(f"布林带宽度: {regime_info.bb_width:.2f}%")
    print(f"趋势方向: {['下跌', '中性', '上涨'][regime_info.trend_direction + 1]}")
    print(f"波动率: {regime_info.volatility:.2%}")

    # 检查是否触发强趋势豁免
    if regime_info.regime == MarketRegime.TRENDING:
        if regime_info.adx >= config.STRONG_TREND_ADX and regime_info.bb_width > config.STRONG_TREND_BB:
            if regime_info.bb_width < 3.0:  # 标准趋势市阈值
                print(f"\n✅ 强趋势豁免触发:")
                print(f"   ADX {regime_info.adx:.1f} >= {config.STRONG_TREND_ADX}")
                print(f"   布林带宽度 {regime_info.bb_width:.2f}% > {config.STRONG_TREND_BB}%")
                print(f"   (虽然低于标准阈值3%，但仍被判定为趋势市)")

    # 推荐策略
    strategies = detector.get_suitable_strategies(regime_info)
    print(f"\n推荐策略:")
    for s in strategies:
        print(f"  - {s}")

    # 是否适合交易
    can_trade, reason = detector.should_trade(regime_info)
    print(f"\n是否适合交易: {'✅ 是' if can_trade else '❌ 否'}")
    print(f"原因: {reason}")

    return regime_info


def test_strong_trend_exemption():
    """测试强趋势豁免逻辑"""
    print_separator("测试强趋势豁免逻辑")

    print("\n场景说明:")
    print("- ADX > 35（强趋势）")
    print("- 布林带宽度在 2%-3% 之间（低于标准阈值但高于豁免阈值）")
    print("- 预期结果: 应该被判定为趋势市")

    print(f"\n配置参数:")
    print(f"- STRONG_TREND_ADX: {config.STRONG_TREND_ADX}")
    print(f"- STRONG_TREND_BB: {config.STRONG_TREND_BB}%")
    print(f"- 标准趋势市阈值: ADX >= 30 且 布林带宽度 > 3%")

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        print("❌ 获取K线数据失败")
        return

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    # 检查是否符合强趋势豁免条件
    if regime_info.adx >= config.STRONG_TREND_ADX and regime_info.bb_width > config.STRONG_TREND_BB:
        if regime_info.bb_width < 3.0:
            if regime_info.regime == MarketRegime.TRENDING:
                print(f"\n✅ 测试通过: 强趋势豁免逻辑正常工作")
                print(f"   ADX: {regime_info.adx:.1f} >= {config.STRONG_TREND_ADX}")
                print(f"   布林带宽度: {regime_info.bb_width:.2f}% (在 {config.STRONG_TREND_BB}% - 3% 之间)")
                print(f"   市场状态: {regime_info.regime.value.upper()}")
            else:
                print(f"\n❌ 测试失败: 应该被判定为趋势市，实际为 {regime_info.regime.value.upper()}")
        else:
            print(f"\n⚠️  当前布林带宽度 {regime_info.bb_width:.2f}% >= 3%，已满足标准趋势市条件")
    else:
        print(f"\n⚠️  当前市场不符合强趋势豁免条件:")
        print(f"   ADX: {regime_info.adx:.1f} (需要 >= {config.STRONG_TREND_ADX})")
        print(f"   布林带宽度: {regime_info.bb_width:.2f}% (需要 > {config.STRONG_TREND_BB}%)")


def test_hysteresis():
    """测试滞回机制"""
    print_separator("测试滞回机制")

    print("\n场景说明:")
    print("- 模拟从趋势市到接近边界的状态转换")
    print("- 验证滞回机制是否能避免频繁切换")

    print(f"\n配置参数:")
    print(f"- 趋势市进入条件: ADX >= 30 且 布林带宽度 > 3%")
    print(f"- 趋势市退出条件: ADX < {config.TREND_EXIT_ADX} 或 布林带宽度 < {config.TREND_EXIT_BB}%")

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        print("❌ 获取K线数据失败")
        return

    # 第一次检测（无历史状态）
    detector1 = MarketRegimeDetector(df, prev_regime=None)
    regime_info1 = detector1.detect()

    print(f"\n第一次检测（无历史状态）:")
    print(f"- 市场状态: {regime_info1.regime.value.upper()}")
    print(f"- ADX: {regime_info1.adx:.1f}")
    print(f"- 布林带宽度: {regime_info1.bb_width:.2f}%")

    # 第二次检测（假设上一次是趋势市）
    detector2 = MarketRegimeDetector(df, prev_regime=MarketRegime.TRENDING)
    regime_info2 = detector2.detect()

    print(f"\n第二次检测（假设上一次是趋势市）:")
    print(f"- 市场状态: {regime_info2.regime.value.upper()}")
    print(f"- ADX: {regime_info2.adx:.1f}")
    print(f"- 布林带宽度: {regime_info2.bb_width:.2f}%")

    # 分析滞回效果
    if regime_info1.regime != regime_info2.regime:
        print(f"\n✅ 滞回机制生效: 状态从 {regime_info1.regime.value.upper()} 保持为 {regime_info2.regime.value.upper()}")
    else:
        print(f"\n⚠️  两次检测结果相同，滞回机制未触发（可能当前市场状态明确）")


def test_confidence_calculation():
    """测试置信度计算"""
    print_separator("测试置信度计算")

    print("\n场景说明:")
    print("- 验证优化后的置信度计算方法")
    print("- ADX 权重 70%，布林带权重 30%")

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        print("❌ 获取K线数据失败")
        return

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    # 手动计算置信度
    adx_score = detector._score_adx(regime_info.adx)
    bb_score = detector._score_bb(regime_info.bb_width)
    expected_confidence = 0.7 * adx_score + 0.3 * bb_score

    print(f"\n当前指标:")
    print(f"- ADX: {regime_info.adx:.1f}")
    print(f"- 布林带宽度: {regime_info.bb_width:.2f}%")

    print(f"\n置信度计算:")
    print(f"- ADX 得分: {adx_score:.2f} (权重 70%)")
    print(f"- 布林带得分: {bb_score:.2f} (权重 30%)")
    print(f"- 预期置信度: {expected_confidence:.2f}")
    print(f"- 实际置信度: {regime_info.confidence:.2f}")

    # 对于过渡市，置信度会打折
    if regime_info.regime == MarketRegime.TRANSITIONING:
        print(f"- 过渡市置信度打折: {expected_confidence:.2f} * 0.6 = {expected_confidence * 0.6:.2f}")


def test_transitioning_threshold():
    """测试过渡市置信度阈值"""
    print_separator("测试过渡市置信度阈值")

    print("\n场景说明:")
    print("- 验证过渡市的交易阈值是否正确设置为 40%")

    print(f"\n配置参数:")
    print(f"- TRANSITIONING_CONFIDENCE_THRESHOLD: {config.TRANSITIONING_CONFIDENCE_THRESHOLD:.0%}")

    trader = BitgetTrader()
    df = trader.get_klines()

    if df.empty:
        print("❌ 获取K线数据失败")
        return

    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    if regime_info.regime == MarketRegime.TRANSITIONING:
        can_trade, reason = detector.should_trade(regime_info)

        print(f"\n当前市场状态: 过渡市")
        print(f"置信度: {regime_info.confidence:.0%}")
        print(f"阈值: {config.TRANSITIONING_CONFIDENCE_THRESHOLD:.0%}")
        print(f"是否适合交易: {'✅ 是' if can_trade else '❌ 否'}")
        print(f"原因: {reason}")

        if regime_info.confidence >= config.TRANSITIONING_CONFIDENCE_THRESHOLD:
            if can_trade:
                print(f"\n✅ 测试通过: 置信度 >= 阈值，允许交易")
            else:
                print(f"\n❌ 测试失败: 置信度 >= 阈值，但不允许交易")
        else:
            if not can_trade:
                print(f"\n✅ 测试通过: 置信度 < 阈值，拒绝交易")
            else:
                print(f"\n❌ 测试失败: 置信度 < 阈值，但允许交易")
    else:
        print(f"\n⚠️  当前市场状态不是过渡市，而是 {regime_info.regime.value.upper()}")
        print(f"   无法测试过渡市阈值逻辑")


def run_all_tests():
    """运行所有测试"""
    print_separator("市场状态检测测试套件")
    print("\n本测试套件用于验证市场状态判断逻辑的优化效果")
    print("包括: 强趋势豁免、滞回机制、置信度计算、过渡市阈值等")

    try:
        # 1. 测试当前市场状态
        regime_info = test_current_market()

        # 2. 测试强趋势豁免
        test_strong_trend_exemption()

        # 3. 测试滞回机制
        test_hysteresis()

        # 4. 测试置信度计算
        test_confidence_calculation()

        # 5. 测试过渡市阈值
        test_transitioning_threshold()

        print_separator("测试完成")
        print("\n✅ 所有测试已完成")

    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
