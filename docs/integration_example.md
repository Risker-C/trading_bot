# 集成示例：如何使用新的升级模块

## 概述

本文档展示如何在 `bot.py` 中集成以下新模块：
1. **交易标签系统** (`trade_tagging.py`)
2. **执行层风控** (`execution_filter.py`)
3. **结构化 Claude 分析** (已更新的 `claude_analyzer.py`)

---

## 完整集成流程

### 1. 在 bot.py 中导入新模块

```python
# 在 bot.py 顶部添加
from trade_tagging import get_tag_manager
from execution_filter import (
    get_execution_filter,
    get_position_sizer,
    get_kill_switch
)
```

### 2. 在 TradingBot.__init__ 中初始化

```python
def __init__(self):
    # ... 现有代码 ...

    # 初始化新模块
    self.tag_manager = get_tag_manager()
    self.execution_filter = get_execution_filter()
    self.position_sizer = get_position_sizer()
    self.kill_switch = get_kill_switch()
```

### 3. 修改 _check_entry_conditions 方法

在现有的信号处理流程中添加新的检查层：

```python
def _check_entry_conditions(self, df, current_price: float):
    """检查开仓条件（增强版）"""

    # 0. 单日亏损熔断检查
    balance = self.trader.get_balance()
    self.kill_switch.reset_daily(balance)

    should_stop, stop_reason = self.kill_switch.should_stop_trading()
    if should_stop:
        logger.warning(f"🔴 {stop_reason}")
        return

    # 1. 风控检查（现有）
    can_open, reason = self.risk_manager.can_open_position()
    if not can_open:
        logger.debug(f"风控限制: {reason}")
        return

    # 2. 市场状态检测（现有）
    detector = MarketRegimeDetector(df)
    regime_info = detector.detect()

    can_trade, trade_reason = detector.should_trade(regime_info)
    if not can_trade:
        logger.debug(f"市场状态不适合交易: {trade_reason}")
        return

    # 3. 动态策略选择（现有）
    if config.USE_DYNAMIC_STRATEGY:
        selected_strategies = detector.get_suitable_strategies(regime_info)
    else:
        selected_strategies = config.ENABLE_STRATEGIES

    # 4. 运行策略
    signals = analyze_all_strategies(df, selected_strategies)

    # 5. 计算技术指标
    ind = IndicatorCalculator(df)
    indicators = {
        'rsi': ind.rsi().iloc[-1] if len(df) >= 14 else 50,
        'macd': ind.macd()['macd'].iloc[-1] if len(df) >= 26 else 0,
        'macd_signal': ind.macd()['signal'].iloc[-1] if len(df) >= 26 else 0,
        'macd_histogram': ind.macd()['histogram'].iloc[-1] if len(df) >= 26 else 0,
        'ema_short': ind.ema(config.EMA_SHORT).iloc[-1] if len(df) >= config.EMA_SHORT else current_price,
        'ema_long': ind.ema(config.EMA_LONG).iloc[-1] if len(df) >= config.EMA_LONG else current_price,
        'bb_upper': ind.bollinger_bands()['upper'].iloc[-1] if len(df) >= 20 else current_price * 1.02,
        'bb_middle': ind.bollinger_bands()['middle'].iloc[-1] if len(df) >= 20 else current_price,
        'bb_lower': ind.bollinger_bands()['lower'].iloc[-1] if len(df) >= 20 else current_price * 0.98,
        'bb_percent_b': ind.bollinger_bands()['percent_b'].iloc[-1] if len(df) >= 20 else 0.5,
        'adx': ind.adx()['adx'].iloc[-1] if len(df) >= 14 else 20,
        'plus_di': ind.adx()['plus_di'].iloc[-1] if len(df) >= 14 else 25,
        'minus_di': ind.adx()['minus_di'].iloc[-1] if len(df) >= 14 else 25,
        'volume_ratio': ind.volume_ratio().iloc[-1] if len(df) >= 20 else 1.0,
        'trend_direction': ind.trend_direction().iloc[-1] if len(df) >= 21 else 0,
        'trend_strength': ind.trend_strength().iloc[-1] if len(df) >= 21 else 0,
        'atr': ind.atr().iloc[-1] if len(df) >= 14 else 0,
        'volatility': ind.volatility().iloc[-1] if len(df) >= 20 else 0.02,
    }

    # 6. 处理每个信号
    for trade_signal in signals:
        if trade_signal.signal not in [Signal.LONG, Signal.SHORT]:
            continue

        # 🆕 创建交易标签
        tag = self.tag_manager.create_tag(
            strategy=trade_signal.strategy,
            signal=trade_signal.signal.value,
            signal_strength=trade_signal.strength,
            signal_confidence=trade_signal.confidence,
            signal_reason=trade_signal.reason,
            signal_indicators=indicators,
            market_regime=regime_info.regime.value,
            market_confidence=regime_info.confidence,
            price=current_price,
            volatility=indicators['volatility']
        )

        # 7. 趋势过滤检查
        trend_pass, trend_reason = self.trend_filter.check_signal(df, trade_signal, indicators)
        self.tag_manager.update_trend_filter(trend_pass, trend_reason)

        if not trend_pass:
            logger.warning(f"❌ 趋势过滤拒绝: {trend_reason}")
            self.tag_manager.save_tag()  # 保存被拒绝的标签
            continue

        # 8. Claude AI 分析
        claude_pass, claude_reason, claude_details = self.claude_analyzer.analyze_signal(
            df, current_price, trade_signal, indicators
        )

        # 更新 Claude 分析结果到标签
        if claude_details:
            self.tag_manager.update_claude_analysis(
                passed=claude_pass,
                confidence=claude_details.get('confidence', 0),
                regime=claude_details.get('regime', ''),
                signal_quality=claude_details.get('signal_quality', 0),
                risk_flags=claude_details.get('risk_flags', []),
                reason=claude_reason,
                suggested_sl=claude_details.get('suggested_sl_pct', 0),
                suggested_tp=claude_details.get('suggested_tp_pct', 0)
            )

        if not claude_pass:
            logger.warning(f"❌ Claude 分析拒绝: {claude_reason}")
            if claude_details.get('warnings'):
                for warning in claude_details['warnings']:
                    logger.warning(f"   ⚠️  {warning}")
            self.tag_manager.save_tag()  # 保存被拒绝的标签
            continue

        # 🆕 9. 执行层风控检查
        ticker = self.trader.get_ticker()
        exec_pass, exec_reason, exec_details = self.execution_filter.check_all(
            df, current_price, ticker, indicators
        )

        self.tag_manager.update_execution_filter(
            passed=exec_pass,
            reason=exec_reason,
            spread_check=exec_details.get('spread_check', True),
            slippage_check=exec_details.get('slippage_check', True),
            liquidity_check=exec_details.get('liquidity_check', True)
        )

        if not exec_pass:
            logger.warning(f"❌ 执行层风控拒绝: {exec_reason}")
            self.tag_manager.save_tag()  # 保存被拒绝的标签
            continue

        # 🆕 10. 计算调整后的仓位
        consecutive_losses = self.risk_manager.metrics.consecutive_losses
        adjusted_position_pct = self.position_sizer.calculate_volatility_adjusted_size(
            current_volatility=indicators['volatility'],
            signal_strength=trade_signal.strength,
            consecutive_losses=consecutive_losses
        )

        logger.info(f"✅ 信号通过所有检查")
        logger.info(f"   调整后仓位: {adjusted_position_pct:.1%} (基础: {config.POSITION_SIZE_PERCENT:.1%})")

        # 11. 执行交易
        if trade_signal.signal == Signal.LONG:
            self._execute_open_long_enhanced(
                trade_signal, current_price, df,
                adjusted_position_pct, indicators
            )
        elif trade_signal.signal == Signal.SHORT:
            self._execute_open_short_enhanced(
                trade_signal, current_price, df,
                adjusted_position_pct, indicators
            )

        return  # 只执行第一个通过的信号

    # 无有效信号
    logger.debug(f"当前价格: {current_price:.2f} - 无有效开仓信号")
```

### 4. 创建增强版的执行方法

```python
def _execute_open_long_enhanced(
    self,
    signal: TradeSignal,
    current_price: float,
    df: pd.DataFrame,
    position_size_pct: float,
    indicators: Dict
):
    """执行开多（增强版）"""
    logger.info(f"📈 开多信号 [{signal.strategy}]: {signal.reason}")

    try:
        # 计算仓位大小
        balance = self.trader.get_balance()
        position_size_usdt = balance * position_size_pct

        # 限制仓位范围
        position_size_usdt = max(config.MIN_ORDER_USDT,
                                min(config.MAX_ORDER_USDT, position_size_usdt))

        # 计算数量
        amount = position_size_usdt * config.LEVERAGE / current_price

        # 下单
        order = self.trader.open_long(amount)

        if order:
            entry_price = order.get('average', current_price)

            # 计算止损止盈
            stop_loss_price = entry_price * (1 - config.STOP_LOSS_PERCENT)
            take_profit_price = entry_price * (1 + config.TAKE_PROFIT_PERCENT)

            # 🆕 标记为已执行
            self.tag_manager.mark_executed(
                executed=True,
                reason="通过所有检查，成功开仓",
                position_size=amount,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )

            # 保存标签
            self.tag_manager.save_tag()

            # 更新风控状态
            self.risk_manager.set_position(
                side='long',
                amount=amount,
                entry_price=entry_price
            )

            self.current_position_side = 'long'
            self.current_strategy = signal.strategy

            logger.info(f"✅ 开多成功: {amount:.4f} @ {entry_price:.2f}")
            logger.info(f"   止损: {stop_loss_price:.2f} | 止盈: {take_profit_price:.2f}")

    except Exception as e:
        logger.error(f"开多失败: {e}")
        # 标记为执行失败
        self.tag_manager.mark_executed(
            executed=False,
            reason=f"执行失败: {str(e)}"
        )
        self.tag_manager.save_tag()
```

### 5. 在平仓时更新标签

```python
def _execute_close_position(self, position, reason: str, close_type: str, current_price: float):
    """执行平仓（增强版）"""
    try:
        # ... 现有平仓逻辑 ...

        # 🆕 如果有当前标签，更新平仓信息
        if self.tag_manager.current_tag:
            pnl = position.get('unrealized_pnl', 0)
            pnl_pct = (current_price - position['entry_price']) / position['entry_price'] * 100

            # 计算 MFE 和 MAE
            if self.risk_manager.position:
                mfe = self.risk_manager.position.highest_price - position['entry_price']
                mae = position['entry_price'] - self.risk_manager.position.lowest_price
            else:
                mfe = mae = 0

            self.tag_manager.mark_closed(
                exit_price=current_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_reason=reason,
                mfe=mfe,
                mae=mae
            )

            self.tag_manager.save_tag()

        # 🆕 更新熔断器
        self.kill_switch.update_pnl(pnl)

    except Exception as e:
        logger.error(f"平仓失败: {e}")
```

---

## 使用示例

### 查询交易标签

```python
from trade_tagging import get_tag_manager

tag_manager = get_tag_manager()

# 查询最近的交易
recent_tags = tag_manager.get_tags(executed_only=True)

for tag in recent_tags[:10]:
    print(f"交易ID: {tag.trade_id}")
    print(f"策略: {tag.strategy}")
    print(f"信号: {tag.signal}")
    print(f"趋势过滤: {'通过' if tag.trend_filter_pass else '拒绝'}")
    print(f"Claude: {'通过' if tag.claude_pass else '拒绝'}")
    print(f"执行: {'是' if tag.executed else '否'}")
    print(f"盈亏: {tag.pnl:.2f} ({tag.pnl_pct:.2f}%)")
    print("-" * 50)
```

### 查询拒绝统计

```python
# 查看哪个阶段拒绝最多
rejection_stats = tag_manager.get_rejection_stats()
print("拒绝统计:")
for stage, count in rejection_stats.items():
    print(f"  {stage}: {count}次")

# 查看 Claude 的准确率
claude_stats = tag_manager.get_claude_accuracy()
print(f"\nClaude 统计:")
print(f"  拒绝次数: {claude_stats['claude_rejects']}")
print(f"  通过次数: {claude_stats['claude_accepts']}")
print(f"  通过后胜率: {claude_stats['claude_win_rate']:.1%}")
```

### 检查执行层风控状态

```python
from execution_filter import get_execution_filter

exec_filter = get_execution_filter()
stats = exec_filter.get_stats()

print("执行层风控统计:")
print(f"  启用: {stats['enabled']}")
print(f"  拒绝次数: {stats['rejection_count']}")
print(f"  最大点差: {stats['thresholds']['max_spread_pct']:.3%}")
print(f"  最小量比: {stats['thresholds']['min_volume_ratio']:.2f}")
```

### 检查熔断器状态

```python
from execution_filter import get_kill_switch

kill_switch = get_kill_switch()
should_stop, reason = kill_switch.should_stop_trading()

if should_stop:
    print(f"⚠️  熔断触发: {reason}")
else:
    remaining = kill_switch.get_remaining_loss_budget()
    print(f"✅ 正常运行，剩余亏损预算: {remaining:.2f} USDT")
```

---

## 验收检查清单

### ✅ 功能验收

- [ ] 每笔交易都创建了 TradeTag
- [ ] 趋势过滤结果被正确记录
- [ ] Claude 分析结果被正确记录
- [ ] 执行层风控结果被正确记录
- [ ] 平仓后 PNL 被正确记录
- [ ] 可以查询历史标签
- [ ] 可以统计拒绝原因
- [ ] 可以计算 Claude 准确率

### ✅ 性能验收

- [ ] 交易标签不影响主循环性能（<10ms）
- [ ] 执行层风控检查快速（<5ms）
- [ ] 数据库写入不阻塞交易

### ✅ 数据验收

- [ ] trade_tags 表正确创建
- [ ] 所有字段都被正确填充
- [ ] JSON 字段可以正确解析
- [ ] 查询性能良好

---

## 故障排查

### 问题 1: 标签未保存

**症状:** 调用 `save_tag()` 后数据库中没有记录

**排查:**
```python
# 检查数据库连接
import sqlite3
conn = sqlite3.connect('trading_bot.db')
cursor = conn.execute("SELECT COUNT(*) FROM trade_tags")
print(f"标签数量: {cursor.fetchone()[0]}")
```

**解决:** 确保 `db.conn.commit()` 被调用

### 问题 2: 执行层风控总是拒绝

**症状:** 所有信号都被执行层风控拒绝

**排查:**
```python
from execution_filter import get_execution_filter

exec_filter = get_execution_filter()
print(f"启用状态: {exec_filter.enabled}")
print(f"阈值: {exec_filter.get_stats()['thresholds']}")
```

**解决:** 调整 config.py 中的阈值

### 问题 3: 熔断器误触发

**症状:** 单日亏损未达到 5% 就触发熔断

**排查:**
```python
from execution_filter import get_kill_switch

kill_switch = get_kill_switch()
print(f"初始余额: {kill_switch.initial_balance}")
print(f"当日盈亏: {kill_switch.daily_pnl}")
print(f"亏损比例: {abs(kill_switch.daily_pnl) / kill_switch.initial_balance:.2%}")
```

**解决:** 确保 `reset_daily()` 在每天开始时被调用

---

## 下一步

1. **测试集成:** 运行 `python test_integration.py`
2. **观察日志:** 查看标签是否正确创建和保存
3. **分析数据:** 使用 SQL 查询分析交易标签
4. **优化参数:** 根据数据调整阈值

完成集成后，你将拥有：
- ✅ 完整的决策链追溯
- ✅ 可量化的过滤效果
- ✅ 数据驱动的优化能力
- ✅ 更稳定的风控体系
