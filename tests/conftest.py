"""
pytest 配置文件

提供测试 fixtures 和配置。
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def sample_kline_data():
    """生成示例 K 线数据"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    data = {
        'timestamp': dates,
        'open': np.random.uniform(40000, 50000, 100),
        'high': np.random.uniform(40000, 50000, 100),
        'low': np.random.uniform(40000, 50000, 100),
        'close': np.random.uniform(40000, 50000, 100),
        'volume': np.random.uniform(100, 1000, 100),
    }
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


@pytest.fixture
def mock_config():
    """模拟配置"""
    return {
        "ENABLE_STRATEGIES": ["bollinger_trend", "macd_cross"],
        "STOP_LOSS_PERCENT": 0.045,
        "TAKE_PROFIT_PERCENT": 0.03,
        "POSITION_SIZE_PERCENT": 0.03,
    }
