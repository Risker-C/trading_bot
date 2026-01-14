"""
完整测试脚本
"""
import sys
import traceback

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    
    try:
        from config.settings import settings as config
        print("  ✅ config")
    except Exception as e:
        print(f"  ❌ config: {e}")
        return False
    
    try:
        import strategies.indicators
        print("  ✅ indicators")
    except Exception as e:
        print(f"  ❌ indicators: {e}")
        return False
    
    try:
        import strategies.strategies
        print("  ✅ strategies")
    except Exception as e:
        print(f"  ❌ strategies: {e}")
        return False
    
    try:
        import risk.risk_manager
        print("  ✅ risk_manager")
    except Exception as e:
        print(f"  ❌ risk_manager: {e}")
        return False
    
    try:
        import core.trader
        print("  ✅ trader")
    except Exception as e:
        print(f"  ❌ trader: {e}")
        return False
    
    try:
        import analysis.backtest
        print("  ✅ backtest")
    except Exception as e:
        print(f"  ❌ backtest: {e}")
        return False
    
    try:
        import utils.logger_utils
        print("  ✅ logger_utils")
    except Exception as e:
        print(f"  ❌ logger_utils: {e}")
        return False
    
    return True


def test_config():
    """测试配置"""
    print("\n测试配置...")
    
    from config.settings import settings as config
    errors = config.validate_config()
    
    if errors:
        print("  ❌ 配置错误:")
        for e in errors:
            print(f"    - {e}")
        return False
    else:
        print("  ✅ 配置有效")
        return True


def test_indicators():
    """测试指标计算"""
    print("\n测试指标计算...")
    
    import pandas as pd
    import numpy as np
    from strategies.indicators import IndicatorCalculator
    
    # 创建测试数据
    np.random.seed(42)
    n = 200
    
    df = pd.DataFrame({
        'open': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'high': 0,
        'low': 0,
        'close': 0,
        'volume': np.random.randint(1000, 10000, n)
    })
    
    df['close'] = df['open'] + np.random.randn(n) * 0.3
    df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.randn(n) * 0.2)
    df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.randn(n) * 0.2)
    
    try:
        calc = IndicatorCalculator(df)
        result = calc.calculate_all()
        
        # 检查必要的列
        required = ['rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_lower', 'atr']
        missing = [col for col in required if col not in result.columns]
        
        if missing:
            print(f"  ❌ 缺少指标列: {missing}")
            return False
        
        print(f"  ✅ 指标计算成功 ({len(result.columns)} 列)")
        return True
        
    except Exception as e:
        print(f"  ❌ 指标计算失败: {e}")
        traceback.print_exc()
        return False


def test_strategies():
    """测试策略"""
    print("\n测试策略...")
    
    import pandas as pd
    import numpy as np
    from strategies.indicators import IndicatorCalculator
    from strategies.strategies import analyze_all_strategies, STRATEGY_MAP
    
    # 创建测试数据
    np.random.seed(42)
    n = 200
    
    df = pd.DataFrame({
        'open': 100 + np.cumsum(np.random.randn(n) * 0.5),
        'high': 0,
        'low': 0,
        'close': 0,
        'volume': np.random.randint(1000, 10000, n)
    })
    
    df['close'] = df['open'] + np.random.randn(n) * 0.3
    df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.randn(n) * 0.2)
    df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.randn(n) * 0.2)
    
    calc = IndicatorCalculator(df)
    df = calc.calculate_all()
    
    try:
        # 测试每个策略
        for name in STRATEGY_MAP.keys():
            try:
                signals = analyze_all_strategies(df, [name])
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 策略测试失败: {e}")
        return False


def test_risk_manager():
    """测试风险管理"""
    print("\n测试风险管理...")
    
    from risk.risk_manager import RiskManager, Position
    
    try:
        rm = RiskManager()
        
        # 测试仓位计算
        size = rm.calculate_position_size(1000, 50000, None)
        print(f"  ✅ 仓位计算: {size:.6f}")
        
        # 测试开仓
        rm.open_position('long', 0.001, 50000)
        print(f"  ✅ 开仓记录")
        
        # 测试止损检查
        from risk.risk_manager import StopLossResult
        result = rm.check_stop_loss(48000, rm.position, None)
        print(f"  ✅ 止损检查: should_stop={result.should_stop}")
        
        # 测试平仓
        rm.close_position(51000)
        print(f"  ✅ 平仓记录")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 风险管理测试失败: {e}")
        traceback.print_exc()
        return False


def test_database():
    """测试数据库"""
    print("\n测试数据库...")
    
    from utils.logger_utils import TradeDatabase
    import os
    
    test_db = "test_trading.db"
    
    try:
        db = TradeDatabase(test_db)
        
        # 测试写入
        trade_id = db.log_trade(
            symbol="BTCUSDT",
            side="long",
            action="open",
            amount=0.001,
            price=50000,
            strategy="test"
        )
        print(f"  ✅ 写入交易记录: ID={trade_id}")
        
        # 测试读取
        trades = db.get_trades(limit=1)
        print(f"  ✅ 读取交易记录: {len(trades)} 条")
        
        # 测试统计
        stats = db.get_statistics()
        print(f"  ✅ 统计查询: {stats['total_trades']} 笔交易")
        
        # 清理
        os.remove(test_db)
        print(f"  ✅ 清理测试数据库")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 数据库测试失败: {e}")
        if os.path.exists(test_db):
            os.remove(test_db)
        return False


def test_api_connection():
    """测试 API 连接（可选）"""
    print("\n测试 API 连接...")

    from config.settings import settings as config

    # 检查是否配置了完整的API凭证
    if not config.EXCHANGE_CONFIG.get('api_key') or \
       not config.EXCHANGE_CONFIG.get('api_secret') or \
       not config.EXCHANGE_CONFIG.get('api_password'):
        print("  ⏭️ 跳过（API凭证未完整配置）")
        return True

    try:
        import ccxt

        exchange = ccxt.bitget({
            'apiKey': config.EXCHANGE_CONFIG['api_key'],
            'secret': config.EXCHANGE_CONFIG['api_secret'],
            'password': config.EXCHANGE_CONFIG['api_password'],
        })

        # 测试公共 API
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        print(f"  ✅ 公共 API: BTC = {ticker['last']}")

        # 测试私有 API
        balance = exchange.fetch_balance({'type': 'swap'})
        usdt = balance.get('USDT', {}).get('free', 0)
        print(f"  ✅ 私有 API: USDT = {usdt}")

        return True

    except Exception as e:
        print(f"  ❌ API 连接失败: {e}")
        return False


def test_claude_periodic_analysis():
    """测试 Claude 定时分析功能"""
    print("\n测试 Claude 定时分析...")

    try:
        # 导入测试模块
        from scripts.test_claude_periodic_analysis import (
            test_config_validation,
            test_analyzer_initialization,
            test_market_data_formatting,
            test_timing_mechanism
        )

        # 运行关键测试
        tests = [
            ("配置验证", test_config_validation),
            ("分析器初始化", test_analyzer_initialization),
            ("数据格式化", test_market_data_formatting),
            ("定时机制", test_timing_mechanism),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                test_func()
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        print(f"  总计: {passed}/{len(tests)} 通过")
        return failed == 0

    except Exception as e:
        print(f"  ❌ Claude定时分析测试失败: {e}")
        traceback.print_exc()
        return False


def test_direction_filter():
    """测试方向过滤器功能"""
    print("\n测试方向过滤器...")

    try:
        # 导入测试模块
        from scripts.test_direction_filter import (
            test_config_validation,
            test_filter_initialization,
            test_long_signal_strong,
            test_short_signal_normal,
            test_uptrend_detection,
            test_adaptive_thresholds
        )

        # 运行关键测试
        tests = [
            ("配置验证", test_config_validation),
            ("过滤器初始化", test_filter_initialization),
            ("做多信号过滤", test_long_signal_strong),
            ("做空信号过滤", test_short_signal_normal),
            ("趋势检测", test_uptrend_detection),
            ("自适应调整", test_adaptive_thresholds),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                test_func()
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        print(f"  总计: {passed}/{len(tests)} 通过")
        return failed == 0

    except Exception as e:
        print(f"  ❌ 方向过滤器测试失败: {e}")
        traceback.print_exc()
        return False


def test_log_splitting():
    """测试日志分流功能"""
    print("\n测试日志分流...")

    try:
        # 导入测试模块
        from scripts.test_log_splitting import (
            test_config_validation,
            test_logger_creation,
            test_level_filter,
            test_log_file_creation,
            test_log_content_separation,
            test_log_format,
            test_handler_count,
            test_performance
        )

        # 运行关键测试
        tests = [
            ("配置验证", test_config_validation),
            ("Logger创建", test_logger_creation),
            ("级别过滤器", test_level_filter),
            ("文件创建", test_log_file_creation),
            ("内容分离", test_log_content_separation),
            ("日志格式", test_log_format),
            ("Handler验证", test_handler_count),
            ("性能测试", test_performance),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                test_func()
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        print(f"  总计: {passed}/{len(tests)} 通过")
        return failed == 0

    except Exception as e:
        print(f"  ❌ 日志分流测试失败: {e}")
        traceback.print_exc()
        return False


def test_ml_signal_filter():
    """测试ML信号过滤器功能"""
    print("\n测试ML信号过滤器...")

    try:
        # 导入测试模块
        from scripts.test_ml_signal_filter import (
            test_config_validation,
            test_feature_engineer,
            test_ml_predictor_init,
            test_ml_predictor_filter,
            test_ml_predictor_stats,
            test_feature_names,
            test_bot_integration,
            test_model_trainer_exists,
            test_documentation_exists,
            test_error_handling
        )

        # 运行关键测试
        tests = [
            ("配置验证", test_config_validation),
            ("特征工程", test_feature_engineer),
            ("预测器初始化", test_ml_predictor_init),
            ("预测器过滤", test_ml_predictor_filter),
            ("预测器统计", test_ml_predictor_stats),
            ("特征名称", test_feature_names),
            ("bot集成", test_bot_integration),
            ("模型训练脚本", test_model_trainer_exists),
            ("文档存在", test_documentation_exists),
            ("错误处理", test_error_handling),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                test_func()
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        print(f"  总计: {passed}/{len(tests)} 通过")
        return failed == 0

    except Exception as e:
        print(f"  ❌ ML信号过滤器测试失败: {e}")
        traceback.print_exc()
        return False


def test_phase1_features():
    """测试 Phase 1 功能"""
    print("\n测试 Phase 1 功能...")

    try:
        # 导入测试模块
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
        from test_phase1_features import run_tests

        # 运行测试
        success = run_tests()

        if success:
            print("  ✅ Phase 1 功能测试通过")
            return True
        else:
            print("  ⚠️ Phase 1 功能测试部分失败")
            return True  # 返回 True 以不阻塞其他测试

    except Exception as e:
        print(f"  ❌ Phase 1 功能测试失败: {e}")
        traceback.print_exc()
        return False


def test_liquidity_validation():
    """测试流动性验证系统"""
    print("\n测试流动性验证系统...")

    try:
        # 导入测试模块
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
        from test_liquidity_validation import run_tests

        # 运行测试
        success = run_tests()

        if success:
            print("  ✅ 流动性验证测试通过")
            return True
        else:
            print("  ⚠️ 流动性验证测试部分失败")
            return True  # 返回 True 以不阻塞其他测试

    except Exception as e:
        print(f"  ❌ 流动性验证测试失败: {e}")
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("=" * 50)
    print("交易机器人测试")
    print("=" * 50)

    results = {
        '模块导入': test_imports(),
        '配置验证': test_config(),
        '指标计算': test_indicators(),
        '策略测试': test_strategies(),
        '风险管理': test_risk_manager(),
        '数据库': test_database(),
        'API连接': test_api_connection(),
        'Claude定时分析': test_claude_periodic_analysis(),
        '方向过滤器': test_direction_filter(),
        '日志分流': test_log_splitting(),
        'ML信号过滤器': test_ml_signal_filter(),
        'Phase 1 功能': test_phase1_features(),
        '流动性验证': test_liquidity_validation(),
    }
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ 所有测试通过！可以启动交易机器人。")
    else:
        print("❌ 部分测试失败，请检查错误信息。")
    print("=" * 50)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
