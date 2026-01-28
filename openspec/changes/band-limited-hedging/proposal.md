# Band-Limited Dynamic Hedging Strategy

## Context

### User Need
用户希望在当前交易系统中添加一个**带不交易区间的动态对冲策略(Band-Limited Dynamic Hedging)**。该策略的核心思想是:
- 通过双向持仓(多+空)降低单边风险
- 利用MES(最小有效操作尺度)阈值过滤噪音交易
- 通过利润迁移机制实现风险再平衡
- 具备明确的退出机制(基于结构失效而非价格止损)

该策略需要先在**回测系统**中实现和验证,然后才能应用于实盘交易。

### Discovered Constraints

#### 技术约束
1. **前端架构**: Next.js + TypeScript + Zustand状态管理
2. **后端架构**: Python + FastAPI + SQLite/Supabase双存储
3. **策略系统**: 基于工厂模式的策略注册机制(`strategies/strategies.py`)
4. **回测引擎**: 事件驱动型回测引擎(`backtest/engine.py`)
5. **数据库Schema**: 已有完整的回测会话、交易、指标表结构

#### 业务约束
1. **策略注册**: 新策略必须注册到`STRATEGY_MAP`
2. **多策略支持**: 前端已支持多策略选择和权重配置
3. **状态管理**: 必须通过`useBacktestStore`管理回测参数
4. **指标计算**: 需要复用现有的`MetricsCalculator`

#### 架构约束
1. **策略基类**: 必须继承`BaseStrategy`并实现`analyze()`方法
2. **信号格式**: 必须返回`TradeSignal`对象
3. **仓位管理**: 回测引擎使用合约模式(95%资金利用率)
4. **手续费模型**: 固定0.1%单边手续费

### Dependencies
- 前端组件依赖: `StrategyMultiSelector`, `WeightConfigList`, `WeightBalancePanel`
- 后端模块依赖: `strategies/strategies.py`, `backtest/engine.py`, `backtest/repository.py`
- 数据库表依赖: `backtest_sessions`, `backtest_trades`, `backtest_metrics`

### Risks
1. **状态复杂度**: 该策略需要维护双向持仓状态,比单向策略复杂
2. **性能影响**: MES阈值判断需要在每个tick执行
3. **退出机制**: 需要新增"优雅退出"逻辑,可能影响现有平仓流程
4. **前端展示**: 双向持仓的可视化需要新的UI组件

## Requirements

### R1: 后端策略实现
**场景**: 作为回测引擎,我需要能够执行Band-Limited Hedging策略

**约束**:
- 策略类名: `BandLimitedHedgingStrategy`
- 继承: `BaseStrategy`
- 注册名: `"band_limited_hedging"`
- 状态变量: `P_ref`(参考价), `qL/pL`(多头), `qS/pS`(空头), `mode`(Active/Pause/Exit)
- 参数: `MES`(最小有效尺度), `alpha`(利润迁移比例), `E_max`(最大风险资本)

**验证**:
```python
# 测试用例
strategy = get_strategy("band_limited_hedging", df, MES=0.006, alpha=0.5)
signal = strategy.analyze()
assert signal.signal.value in ['long', 'short', 'close_long', 'close_short', 'hold']
```

### R2: 状态机实现
**场景**: 策略需要在Active/Pause/Exit三种模式间切换

**约束**:
- Active模式: 正常再平衡
- Pause模式: 冻结新仓位,仅监控
- Exit模式: 分阶段减仓(每次减少eta比例)
- 触发条件: 基于`sigma_eff`, `E_t`, `tau`等内生变量

**验证**:
- 模式转换逻辑可测试
- Exit模式下交易次数有上界

### R3: 前端策略选择支持
**场景**: 用户在回测配置页面选择Band-Limited Hedging策略

**约束**:
- 在`AVAILABLE_STRATEGIES`中添加新策略
- 策略参数表单需要支持`MES`, `alpha`, `E_max`等参数
- 参数验证: `MES > 0`, `0 < alpha < 1`, `E_max > 0`

**验证**:
- 策略出现在下拉列表
- 参数输入框正确渲染
- 参数验证生效

### R4: 回测结果展示
**场景**: 回测完成后,展示双向持仓的盈亏情况

**约束**:
- 交易记录需要区分多头/空头
- 指标计算需要考虑双向持仓的净暴露
- 权益曲线需要反映未实现盈亏

**验证**:
- 交易列表正确显示side字段
- 指标计算准确
- 权益曲线连续

### R5: 退出机制实现
**场景**: 当结构失效时,策略需要优雅退出

**约束**:
- 退出触发条件: `sigma_eff^2 < MES * f` 或 `E_t > E_max`
- 退出方式: 分阶段减仓,每次减少`eta`比例
- 退出完成: `qL + qS < epsilon`

**验证**:
- 退出逻辑可测试
- 退出成本有上界
- 不会出现强制清仓

## Success Criteria

### 功能完整性
- [ ] 策略类实现并注册到`STRATEGY_MAP`
- [ ] 状态机逻辑完整(Active/Pause/Exit)
- [ ] 前端策略选择器包含新策略
- [ ] 回测引擎能正确执行该策略
- [ ] 退出机制正常工作

### 数据正确性
- [ ] 双向持仓状态正确维护
- [ ] MES阈值判断准确
- [ ] 利润迁移计算正确
- [ ] 手续费扣除准确
- [ ] 指标计算无误

### 用户体验
- [ ] 策略参数表单易用
- [ ] 回测结果清晰展示
- [ ] 交易记录可追溯
- [ ] 错误提示友好

### 性能要求
- [ ] 单次回测耗时 < 30秒(1个月15分钟K线)
- [ ] 内存占用 < 500MB
- [ ] 数据库写入无阻塞

## Implementation Sequence

1. **后端策略实现** (P0)
   - 实现`BandLimitedHedgingStrategy`类
   - 注册到`STRATEGY_MAP`
   - 单元测试

2. **状态机逻辑** (P0)
   - 实现模式转换逻辑
   - 实现退出机制
   - 集成测试

3. **前端策略选择** (P1)
   - 更新`AVAILABLE_STRATEGIES`
   - 添加参数表单
   - 参数验证

4. **回测集成** (P1)
   - 修改`backtest/engine.py`支持双向持仓
   - 更新指标计算
   - 端到端测试

5. **UI优化** (P2)
   - 双向持仓可视化
   - 退出状态展示
   - 文档完善

## User Decisions (已确认)

1. **MES默认值**: ✅ `MES = 6 * fee_rate` (0.006 for 0.1% fee)
2. **alpha默认值**: ✅ `alpha = 0.5` (50%利润修复亏损侧,50%重建结构)
3. **多策略组合**: ✅ 仅支持单独运行,不与其他策略加权组合
4. **前端展示**: ✅ 复用现有交易列表,通过side字段区分多空

## Open Questions (待技术验证)

1. **Exit触发阈值**: `gamma1`, `gamma2`的合理范围? (建议: gamma1=1.0, gamma2=0.85)
2. **实盘应用**: 该策略何时可以应用于实盘? (建议: 至少100次回测验证后)
3. **性能优化**: 是否需要缓存MES阈值判断结果?

