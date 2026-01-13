"""
TradingEngine 单元测试
"""

import pytest
from unittest.mock import Mock, MagicMock
from core.engine import TradingEngine


class TestTradingEngine:
    """TradingEngine 测试类"""

    @pytest.fixture
    def mock_engines(self):
        """创建模拟的四个引擎"""
        return {
            "strategy": Mock(),
            "risk": Mock(),
            "execution": Mock(),
            "monitoring": Mock(),
        }

    @pytest.fixture
    def trading_engine(self, mock_engines):
        """创建 TradingEngine 实例"""
        return TradingEngine(
            strategy_engine=mock_engines["strategy"],
            risk_engine=mock_engines["risk"],
            execution_engine=mock_engines["execution"],
            monitoring_engine=mock_engines["monitoring"],
        )

    def test_engine_initialization(self, trading_engine):
        """测试引擎初始化"""
        assert trading_engine is not None
        assert trading_engine.running is False

    def test_engine_start_stop(self, trading_engine, mock_engines):
        """测试引擎启动和停止"""
        # 启动
        trading_engine.start()
        assert trading_engine.running is True
        mock_engines["monitoring"].update_status.assert_called()

        # 停止
        trading_engine.stop()
        assert trading_engine.running is False

    def test_run_cycle_no_signal(self, trading_engine, mock_engines, sample_kline_data):
        """测试无信号的交易周期"""
        # 模拟策略引擎返回 None
        mock_engines["strategy"].generate_signal.return_value = None

        result = trading_engine.run_cycle(sample_kline_data)

        assert result["success"] is False
        assert result["action"] is None
        mock_engines["strategy"].generate_signal.assert_called_once()

    def test_run_cycle_risk_rejected(self, trading_engine, mock_engines, sample_kline_data):
        """测试风控拒绝的交易周期"""
        # 模拟策略引擎返回信号
        mock_signal = Mock()
        mock_engines["strategy"].generate_signal.return_value = mock_signal

        # 模拟风控拒绝
        mock_engines["risk"].can_open_position.return_value = (False, "风险过高")

        result = trading_engine.run_cycle(sample_kline_data)

        assert result["success"] is False
        mock_engines["monitoring"].update_status.assert_called()

    def test_run_cycle_success(self, trading_engine, mock_engines, sample_kline_data):
        """测试成功执行的交易周期"""
        # 模拟策略引擎返回信号
        mock_signal = Mock()
        mock_engines["strategy"].generate_signal.return_value = mock_signal

        # 模拟风控通过
        mock_engines["risk"].can_open_position.return_value = (True, "")

        # 模拟执行成功
        mock_engines["execution"].execute_signal.return_value = True

        result = trading_engine.run_cycle(sample_kline_data)

        assert result["success"] is True
        assert result["action"] == "executed"
        mock_engines["execution"].execute_signal.assert_called_once()

    def test_get_status(self, trading_engine, mock_engines):
        """测试获取状态"""
        mock_engines["strategy"].get_active_strategies.return_value = ["strategy1"]
        mock_engines["monitoring"].get_status.return_value = {"status": "ok"}

        status = trading_engine.get_status()

        assert "running" in status
        assert "strategies" in status
        assert "monitoring" in status
