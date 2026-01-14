"""
配置验证模块 - 使用 Pydantic 进行类型安全验证
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class RiskConfig(BaseModel):
    """风险管理配置"""
    stop_loss_percent: float = Field(0.045, ge=0.01, le=0.1, description="止损比例 (1%-10%)")
    take_profit_percent: float = Field(0.03, ge=0.01, le=0.2, description="止盈比例 (1%-20%)")
    trailing_stop_percent: float = Field(0.03, ge=0.005, le=0.1, description="移动止损比例 (0.5%-10%)")
    leverage: int = Field(10, ge=1, le=125, description="杠杆倍数 (1-125)")
    position_size_percent: float = Field(0.03, ge=0.01, le=0.5, description="仓位比例 (1%-50%)")

    @field_validator('leverage')
    @classmethod
    def validate_leverage(cls, v):
        """验证杠杆倍数合理性"""
        if v > 20:
            print(f"⚠️ 警告: 杠杆倍数 {v}x 较高，风险较大")
        return v

    @field_validator('position_size_percent')
    @classmethod
    def validate_position_size(cls, v, info):
        """验证仓位与杠杆的组合风险"""
        leverage = info.data.get('leverage', 10)
        max_loss = v * leverage * info.data.get('stop_loss_percent', 0.045)
        if max_loss > 0.02:  # 单笔最大损失 > 2%
            print(f"⚠️ 警告: 单笔最大损失 {max_loss*100:.2f}% 较高")
        return v


class ExchangeConfig(BaseModel):
    """交易所配置"""
    api_key: str = Field(..., min_length=10, description="API Key")
    api_secret: str = Field(..., min_length=10, description="API Secret")
    api_password: Optional[str] = Field(None, description="API Password (部分交易所需要)")
    symbol: str = Field("BTCUSDT", description="交易对")
    leverage: int = Field(10, ge=1, le=125)
    margin_mode: str = Field("crossed", description="保证金模式")

    @field_validator('margin_mode')
    @classmethod
    def validate_margin_mode(cls, v):
        """验证保证金模式"""
        if v not in ['crossed', 'isolated']:
            raise ValueError(f"保证金模式必须是 'crossed' 或 'isolated'，当前: {v}")
        return v


class StrategyConfig(BaseModel):
    """策略配置"""
    enable_strategies: List[str] = Field(
        default=["bollinger_trend", "macd_cross", "ema_cross"],
        description="启用的策略列表"
    )
    min_signal_strength: float = Field(0.5, ge=0.0, le=1.0, description="最小信号强度")
    min_strategy_agreement: float = Field(0.5, ge=0.0, le=1.0, description="最小策略一致性")

    @field_validator('enable_strategies')
    @classmethod
    def validate_strategies(cls, v):
        """验证策略列表不为空"""
        if not v:
            raise ValueError("至少需要启用一个策略")
        return v


def validate_config(config_module):
    """
    验证配置模块

    Args:
        config_module: 配置模块对象

    Returns:
        bool: 验证是否通过
    """
    try:
        # 验证风险配置
        risk_config = RiskConfig(
            stop_loss_percent=config_module.STOP_LOSS_PERCENT,
            take_profit_percent=config_module.TAKE_PROFIT_PERCENT,
            trailing_stop_percent=config_module.TRAILING_STOP_PERCENT,
            leverage=config_module.LEVERAGE,
            position_size_percent=config_module.POSITION_SIZE_PERCENT,
        )
        print("✅ 风险配置验证通过")

        # 验证策略配置
        strategy_config = StrategyConfig(
            enable_strategies=config_module.ENABLE_STRATEGIES,
            min_signal_strength=getattr(config_module, 'MIN_SIGNAL_STRENGTH', 0.5),
            min_strategy_agreement=getattr(config_module, 'MIN_STRATEGY_AGREEMENT', 0.5),
        )
        print("✅ 策略配置验证通过")

        return True

    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        return False


if __name__ == "__main__":
    # 测试配置验证
    from config.settings import settings as config
    validate_config(config)
