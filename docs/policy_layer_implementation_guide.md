# Policy Layer 实施指南

## 📋 概述

本文档详细说明如何完成 Policy Layer（策略治理层）的集成，将 Claude 从"分析旁观者"升级为"策略调度与参数治理层"。

## ✅ 已完成的工作

### 1. 核心模块创建

- ✅ `policy_layer.py` - Policy Layer 核心模块
- ✅ `claude_policy_analyzer.py` - Claude 策略治理分析器

### 2. 核心功能实现

- ✅ 市场制度判断（Regime Detection）
- ✅ 风控模式切换（Risk Mode Switching）
- ✅ 参数边界验证（Parameter Validation）
- ✅ 决策历史记录（Decision History）
- ✅ TTL 过期机制（Time-To-Live）

## 🔄 待完成的集成步骤

### 步骤 1: 更新 config.py

在 `config.py` 文件的第 325 行之后（Claude每日报告配置之后）添加以下配置：

```python
# ==================== Policy Layer 配置（新增）====================

# 是否启用 Policy Layer（策略治理层）
ENABLE_POLICY_LAYER = True

# Policy Layer 更新间隔（分钟）
# Claude 会定期分析交易上下文并更新策略参数
POLICY_UPDATE_INTERVAL = 30  # 默认30分钟

# Policy Layer 模式
# "shadow": 影子模式（只记录不生效，用于观察）
# "active": 主动模式（真实影响交易参数）
POLICY_LAYER_MODE = "active"  # 建议先用 "shadow" 观察1-2天

# 是否在启动时立即执行一次 Policy 分析
POLICY_ANALYZE_ON_STARTUP = True

# Policy 决策的默认 TTL（分钟）
POLICY_DEFAULT_TTL = 30

# Policy Layer 参数边界（安全约束）
POLICY_PARAM_BOUNDS = {
    'stop_loss_pct': (0.005, 0.05),      # 0.5% - 5%
    'take_profit_pct': (0.01, 0.10),     # 1% - 10%
    'trailing_stop_pct': (0.005, 0.03),  # 0.5% - 3%
    'position_multiplier': (0.3, 2.0),   # 0.3x - 2.0x
}

# 风控模式自动切换规则
POLICY_AUTO_RISK_MODE = True  # 是否允许自动切换风控模式

# 连续亏损触发防守模式的阈值
POLICY_DEFENSIVE_LOSS_THRESHOLD = 3

# 连续盈利触发激进模式的阈值
POLICY_AGGRESSIVE_WIN_THRESHOLD = 5
```

### 步骤 2: 创建 trading_context_builder.py

创建新文件 `/root/trading_bot/trading_context_builder.py`：

```python
"""
Trading Context Builder - 交易上下文构建器

负责从系统各个模块收集信息，构建完整的 TradingContext
"""

from datetime import datetime
from typing import Dict, Optional
import pandas as pd

from policy_layer import TradingContext, MarketRegime, RiskMode
from risk_manager import RiskManager
import config
from logger_utils import get_logger

logger = get_logger("context_builder")


class TradingContextBuilder:
    """交易上下文构建器"""

    def __init__(self, risk_manager: RiskManager):
        """
        初始化

        Args:
            risk_manager: 风险管理器实例
        """
        self.risk_manager = risk_manager

    def build_context(
        self,
        df: pd.DataFrame,
        current_price: float,
        indicators: Dict
    ) -> TradingContext:
        """
        构建完整的交易上下文

        Args:
            df: K线数据
            current_price: 当前价格
            indicators: 技术指标

        Returns:
            TradingContext 对象
        """
        context = TradingContext()

        # A. 历史交易状态
        context.recent_trades_count = self.risk_manager.metrics.total_trades
        context.win_rate = self.risk_manager.metrics.win_rate
        context.recent_pnl = self.risk_manager.metrics.total_pnl
        context.consecutive_losses = self.risk_manager.metrics.consecutive_losses
        context.consecutive_wins = self.risk_manager.metrics.consecutive_wins
        context.avg_win = self.risk_manager.metrics.avg_win
        context.avg_loss = self.risk_manager.metrics.avg_loss

        # B. 当前持仓状态
        if self.risk_manager.position:
            pos = self.risk_manager.position
            context.has_position = True
            context.position_side = pos.side
            context.position_amount = pos.amount
            context.entry_price = pos.entry_price
            context.current_price = current_price
            context.unrealized_pnl = pos.unrealized_pnl
            context.unrealized_pnl_pct = pos.unrealized_pnl_pct

            # 计算持仓时间
            if pos.entry_time:
                holding_time = datetime.now() - pos.entry_time
                context.holding_time_minutes = holding_time.total_seconds() / 60

            context.current_stop_loss = pos.stop_loss_price
            context.current_take_profit = pos.take_profit_price

        # C. 实时市场结构
        context.market_regime = self._detect_market_regime(indicators)
        context.trend_direction = self._get_trend_direction(indicators)
        context.volatility = self.risk_manager.metrics.volatility
        context.adx = self._get_indicator_value(indicators, 'adx', 0.0)
        context.volume_ratio = self._get_indicator_value(indicators, 'volume_ratio', 1.0)

        # D. 系统状态
        context.current_risk_mode = self._determine_risk_mode()
        context.daily_pnl = self.risk_manager.daily_pnl
        context.daily_trades = self.risk_manager.daily_trades

        context.current_price = current_price

        return context

    def _detect_market_regime(self, indicators: Dict) -> MarketRegime:
        """
        检测市场制度

        Args:
            indicators: 技术指标

        Returns:
            MarketRegime
        """
        adx = self._get_indicator_value(indicators, 'adx', 0.0)
        ema_short = self._get_indicator_value(indicators, 'ema_short', 0.0)
        ema_long = self._get_indicator_value(indicators, 'ema_long', 0.0)
        bb_percent = self._get_indicator_value(indicators, 'bb_percent_b', 0.5)

        # 强趋势市
        if adx > 25 and abs(ema_short - ema_long) / ema_long > 0.01:
            return MarketRegime.TREND

        # 震荡市
        if adx < 20 and 0.2 < bb_percent < 0.8:
            return MarketRegime.MEAN_REVERT

        # 混乱市
        if adx < 15:
            return MarketRegime.CHOP

        return MarketRegime.UNKNOWN

    def _get_trend_direction(self, indicators: Dict) -> int:
        """
        获取趋势方向

        Args:
            indicators: 技术指标

        Returns:
            1=上涨, -1=下跌, 0=震荡
        """
        ema_short = self._get_indicator_value(indicators, 'ema_short', 0.0)
        ema_long = self._get_indicator_value(indicators, 'ema_long', 0.0)
        macd = self._get_indicator_value(indicators, 'macd', 0.0)

        if ema_short > ema_long and macd > 0:
            return 1
        elif ema_short < ema_long and macd < 0:
            return -1
        else:
            return 0

    def _determine_risk_mode(self) -> RiskMode:
        """
        确定当前风控模式

        Returns:
            RiskMode
        """
        # 根据连续亏损/盈利判断
        if self.risk_manager.metrics.consecutive_losses >= config.POLICY_DEFENSIVE_LOSS_THRESHOLD:
            return RiskMode.DEFENSIVE
        elif self.risk_manager.metrics.consecutive_wins >= config.POLICY_AGGRESSIVE_WIN_THRESHOLD:
            return RiskMode.AGGRESSIVE
        elif self.risk_manager.metrics.consecutive_losses > 0:
            return RiskMode.RECOVERY
        else:
            return RiskMode.NORMAL

    def _get_indicator_value(self, indicators: Dict, key: str, default: float) -> float:
        """
        安全获取指标值

        Args:
            indicators: 指标字典
            key: 指标键
            default: 默认值

        Returns:
            指标值
        """
        value = indicators.get(key, default)
        if hasattr(value, 'iloc'):
            return float(value.iloc[-1]) if len(value) > 0 else default
        return float(value) if value is not None else default


def get_context_builder(risk_manager: RiskManager) -> TradingContextBuilder:
    """获取上下文构建器实例"""
    return TradingContextBuilder(risk_manager)
```

### 步骤 3: 更新 risk_manager.py

在 `risk_manager.py` 的 `RiskManager` 类中添加以下方法（在 `__init__` 方法之后）：

```python
def get_policy_adjusted_stop_loss(self, entry_price: float, side: str, df: pd.DataFrame = None) -> float:
    """
    获取 Policy Layer 调整后的止损价格

    Args:
        entry_price: 入场价
        side: 方向
        df: K线数据

    Returns:
        止损价格
    """
    from policy_layer import get_policy_layer

    policy = get_policy_layer()
    stop_loss_pct = policy.get_stop_loss_percent()

    if side == 'long':
        return entry_price * (1 - stop_loss_pct / config.LEVERAGE)
    else:
        return entry_price * (1 + stop_loss_pct / config.LEVERAGE)

def get_policy_adjusted_take_profit(self, entry_price: float, side: str) -> float:
    """
    获取 Policy Layer 调整后的止盈价格

    Args:
        entry_price: 入场价
        side: 方向

    Returns:
        止盈价格
    """
    from policy_layer import get_policy_layer

    policy = get_policy_layer()
    take_profit_pct = policy.get_take_profit_percent()

    if side == 'long':
        return entry_price * (1 + take_profit_pct / config.LEVERAGE)
    else:
        return entry_price * (1 - take_profit_pct / config.LEVERAGE)

def get_policy_adjusted_position_size(self, base_amount: float) -> float:
    """
    获取 Policy Layer 调整后的仓位大小

    Args:
        base_amount: 基础仓位数量

    Returns:
        调整后的仓位数量
    """
    from policy_layer import get_policy_layer

    policy = get_policy_layer()
    multiplier = policy.get_position_size_multiplier()

    return base_amount * multiplier
```

然后修改 `calculate_stop_loss` 方法（第 326 行）：

```python
def calculate_stop_loss(
    self,
    entry_price: float,
    side: str,
    df: pd.DataFrame = None
) -> float:
    """
    计算止损价格
    支持固定止损和 ATR 动态止损
    **现在会使用 Policy Layer 的参数**
    """
    # 检查是否启用 Policy Layer
    if getattr(config, 'ENABLE_POLICY_LAYER', False):
        return self.get_policy_adjusted_stop_loss(entry_price, side, df)

    # 原有逻辑保持不变
    if config.USE_ATR_STOP_LOSS and df is not None:
        return self._calculate_atr_stop_loss(entry_price, side, df)
    else:
        return self._calculate_fixed_stop_loss(entry_price, side)
```

类似地修改 `calculate_take_profit` 方法（第 385 行）：

```python
def calculate_take_profit(
    self,
    entry_price: float,
    side: str,
    risk_reward_ratio: float = 2.0
) -> float:
    """
    计算止盈价格
    **现在会使用 Policy Layer 的参数**
    """
    # 检查是否启用 Policy Layer
    if getattr(config, 'ENABLE_POLICY_LAYER', False):
        return self.get_policy_adjusted_take_profit(entry_price, side)

    # 原有逻辑保持不变
    stop_loss = self.calculate_stop_loss(entry_price, side)
    risk = abs(entry_price - stop_loss)
    reward = risk * risk_reward_ratio

    if side == 'long':
        take_profit = entry_price + reward
    else:
        take_profit = entry_price - reward

    fixed_tp = entry_price * (1 + config.TAKE_PROFIT_PERCENT / config.LEVERAGE) if side == 'long' \
               else entry_price * (1 - config.TAKE_PROFIT_PERCENT / config.LEVERAGE)

    if side == 'long':
        take_profit = max(take_profit, fixed_tp)
    else:
        take_profit = min(take_profit, fixed_tp)

    return take_profit
```

修改 `calculate_position_size` 方法（第 221 行），在返回之前添加 Policy Layer 调整：

```python
def calculate_position_size(
    self,
    balance: float,
    current_price: float,
    df: pd.DataFrame = None,
    signal_strength: float = 1.0
) -> float:
    """
    计算仓位大小
    综合考虑: Kelly公式、波动率、信号强度、**Policy Layer 调整**
    """
    # ... 原有逻辑保持不变 ...

    # 转换为合约数量
    amount = position_value / current_price

    # Policy Layer 调整（新增）
    if getattr(config, 'ENABLE_POLICY_LAYER', False):
        amount = self.get_policy_adjusted_position_size(amount)
        logger.debug(f"Policy Layer 仓位调整后: {amount:.6f}")

    logger.info(f"计算仓位: 余额={balance:.2f}, 比例={base_ratio:.2%}, "
               f"价值={position_value:.2f}, 数量={amount:.6f}")

    return amount
```

### 步骤 4: 更新 bot.py（主程序集成）

在 `bot.py` 中添加 Policy Layer 集成。找到主循环部分，添加以下代码：

```python
# 在文件顶部导入
from policy_layer import get_policy_layer
from claude_policy_analyzer import get_claude_policy_analyzer
from trading_context_builder import get_context_builder

# 在 Bot 类的 __init__ 方法中初始化
def __init__(self):
    # ... 现有初始化代码 ...

    # 初始化 Policy Layer（新增）
    if getattr(config, 'ENABLE_POLICY_LAYER', False):
        self.policy_layer = get_policy_layer()
        self.policy_analyzer = get_claude_policy_analyzer()
        self.context_builder = get_context_builder(self.risk_manager)
        self.last_policy_update = None
        logger.info("✅ Policy Layer 已启用")
    else:
        self.policy_layer = None
        self.policy_analyzer = None
        self.context_builder = None
        logger.info("⚠️ Policy Layer 未启用")

# 在主循环中添加 Policy Layer 更新逻辑
def run(self):
    """主运行循环"""
    while True:
        try:
            # ... 现有代码 ...

            # Policy Layer 定期更新（新增）
            if self.policy_layer and self._should_update_policy():
                self._update_policy_layer(df, current_price, indicators)

            # ... 现有代码继续 ...

        except Exception as e:
            logger.error(f"主循环异常: {e}")
            time.sleep(config.CHECK_INTERVAL)

def _should_update_policy(self) -> bool:
    """判断是否应该更新 Policy"""
    if not self.last_policy_update:
        return True

    interval = getattr(config, 'POLICY_UPDATE_INTERVAL', 30) * 60
    elapsed = (datetime.now() - self.last_policy_update).total_seconds()
    return elapsed >= interval

def _update_policy_layer(self, df, current_price, indicators):
    """更新 Policy Layer"""
    try:
        logger.info("🔄 开始 Policy Layer 更新...")

        # 1. 构建交易上下文
        context = self.context_builder.build_context(df, current_price, indicators)

        # 2. 调用 Claude 进行策略治理分析
        decision = self.policy_analyzer.analyze_for_policy(context, df, indicators)

        if not decision:
            logger.warning("Policy 分析失败，保持当前参数")
            return

        # 3. 验证并应用决策
        mode = getattr(config, 'POLICY_LAYER_MODE', 'active')

        if mode == 'shadow':
            # 影子模式：只记录不生效
            logger.info(f"🔍 [Shadow Mode] Policy 决策: {decision.reason}")
            logger.info(f"   止损建议: {decision.suggested_stop_loss_pct:.2%}" if decision.suggested_stop_loss_pct else "   止损建议: 无调整")
            logger.info(f"   止盈建议: {decision.suggested_take_profit_pct:.2%}" if decision.suggested_take_profit_pct else "   止盈建议: 无调整")
        else:
            # 主动模式：真实应用
            success, reason, actions = self.policy_layer.validate_and_apply_decision(decision, context)

            if success:
                logger.info(f"✅ Policy 决策已应用: {reason}")
                # 可选：推送到飞书
                if getattr(config, 'ENABLE_FEISHU', False):
                    self._notify_policy_update(decision, actions)
            else:
                logger.warning(f"⚠️ Policy 决策未应用: {reason}")

        self.last_policy_update = datetime.now()

    except Exception as e:
        logger.error(f"Policy Layer 更新失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())

def _notify_policy_update(self, decision, actions):
    """通知 Policy 更新（可选）"""
    from logger_utils import notifier

    message = f"""🤖 Policy Layer 参数更新

市场制度: {decision.regime.value}
风控模式: {decision.suggested_risk_mode.value if decision.suggested_risk_mode else 'N/A'}

应用的调整:
"""
    for action in actions:
        message += f"• {action.value}\n"

    message += f"\n原因: {decision.reason}"

    notifier.feishu.send_message(message)
```

### 步骤 5: 测试和验证

创建测试文件 `/root/trading_bot/scripts/test_policy_layer.py`：

```python
#!/usr/bin/env python3
"""
Policy Layer 测试脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from policy_layer import *
from claude_policy_analyzer import get_claude_policy_analyzer
import config

def test_policy_layer_basic():
    """测试 Policy Layer 基本功能"""
    print("\n=== 测试 1: Policy Layer 基本功能 ===")

    policy = get_policy_layer()

    # 测试获取参数
    print(f"当前止损: {policy.get_stop_loss_percent():.2%}")
    print(f"当前止盈: {policy.get_take_profit_percent():.2%}")
    print(f"当前仓位倍数: {policy.get_position_size_multiplier():.2f}x")
    print(f"当前风控模式: {policy.get_risk_mode().value}")

    print("✅ 基本功能测试通过")

def test_policy_decision():
    """测试 Policy Decision"""
    print("\n=== 测试 2: Policy Decision ===")

    # 创建测试决策
    decision = PolicyDecision(
        regime=MarketRegime.TREND,
        regime_confidence=0.8,
        suggested_stop_loss_pct=0.025,
        suggested_take_profit_pct=0.05,
        confidence=0.75,
        reason="测试决策"
    )

    print(f"决策制度: {decision.regime.value}")
    print(f"止损建议: {decision.suggested_stop_loss_pct:.2%}")
    print(f"是否过期: {decision.is_expired()}")

    print("✅ Policy Decision 测试通过")

def test_policy_validation():
    """测试参数验证"""
    print("\n=== 测试 3: 参数边界验证 ===")

    policy = get_policy_layer()
    context = TradingContext()

    # 测试超出边界的参数
    decision = PolicyDecision(
        regime=MarketRegime.TREND,
        suggested_stop_loss_pct=0.10,  # 超出上限
        confidence=0.8,
        reason="边界测试"
    )

    success, reason, actions = policy.validate_and_apply_decision(decision, context)

    print(f"应用结果: {success}")
    print(f"原因: {reason}")
    print(f"实际止损: {policy.get_stop_loss_percent():.2%}")

    print("✅ 参数验证测试通过")

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("Policy Layer 测试")
    print("="*60)

    try:
        test_policy_layer_basic()
        test_policy_decision()
        test_policy_validation()

        print("\n" + "="*60)
        print("✅ 所有测试通过")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

添加执行权限：
```bash
chmod +x scripts/test_policy_layer.py
```

### 步骤 6: 部署和监控

1. **影子模式测试（1-2天）**
   ```python
   # config.py
   POLICY_LAYER_MODE = "shadow"  # 只记录不生效
   ```

2. **主动模式部署**
   ```python
   # config.py
   POLICY_LAYER_MODE = "active"  # 真实影响交易
   ```

3. **监控指标**
   - Policy 决策应用成功率
   - 参数调整频率
   - 止损/止盈触发率变化
   - 整体盈亏表现

## 🎯 预期效果

### 问题 1: Claude 建议都是"观望" → ✅ 解决
- Claude 现在有完整的交易上下文（历史、持仓、系统状态）
- 职责从"EXECUTE/REJECT"变为"调参数/切策略"
- 即使市场不适合开仓，也会调整风控参数

### 问题 2: 持仓都是止损出局 → ✅ 解决
- Policy Layer 可以动态调整止损宽度
- 根据市场制度放宽/收紧止损
- 盈利时启用移动止损保护利润

### 问题 3: 移动止损不生效 → ✅ 解决
- Policy Layer 可以控制移动止损的启用/禁用
- 根据市场状态调整移动止损百分比

## ⚠️ 重要提示

1. **先用 Shadow 模式观察 1-2 天**
2. **所有参数变更都有边界约束**
3. **决策有 TTL，会自动过期恢复默认**
4. **可以随时强制重置: `policy.force_reset()`**

## 📞 故障排查

如果遇到问题：

1. 检查日志中的 Policy Layer 相关信息
2. 查看 `policy.get_status_report()` 的输出
3. 确认 Claude API 调用是否成功
4. 验证 TradingContext 是否正确构建

## 🔄 后续优化方向

1. 添加 Policy 决策的回测功能
2. 实现策略组合的动态切换
3. 增加更多市场制度的识别
4. 优化参数调整的响应速度

---

**文档版本**: v1.0
**创建日期**: 2025-12-17
**作者**: Claude Sonnet 4.5
