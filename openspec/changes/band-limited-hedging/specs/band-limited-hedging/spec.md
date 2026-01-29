# Capability: Band-Limited Hedging (Backtest)

## ADDED Requirements

### Requirement: 策略可在回测中选择并执行
系统 SHALL 在回测流程中提供 `band_limited_hedging` 策略选项，并可被单策略模式执行。

#### Scenario: 单策略选择
- **WHEN** 用户在回测配置中选择 `band_limited_hedging`
- **THEN** 回测请求包含 `strategy_name = band_limited_hedging`
- **AND** 后端加载对应策略实现执行回测

### Requirement: 参数校验与默认值
系统 SHALL 支持策略参数 `MES`, `alpha`, `E_max`，并进行校验与默认值填充。

#### Scenario: 合法参数
- **WHEN** `MES > 0` 且 `0 < alpha < 1` 且 `E_max > 0`
- **THEN** 回测请求可被接受并进入执行

#### Scenario: 非法参数
- **WHEN** `MES <= 0` 或 `alpha <= 0` 或 `alpha >= 1` 或 `E_max <= 0`
- **THEN** 系统返回可理解的错误提示

### Requirement: 不交易区间与再平衡
策略 SHALL 维护参考价 `P_ref` 与双向持仓状态 `qL/pL`, `qS/pS`，并在**相对价格偏移**满足阈值时触发再平衡。

#### Scenario: 价格在 MES 区间内
- **WHEN** `|P_t - P_ref| / P_ref < MES`
- **THEN** 不产生交易信号，状态保持不变

#### Scenario: 价格穿越 MES 触发再平衡
- **WHEN** `|P_t - P_ref| / P_ref >= MES`
- **THEN** 执行一次“平仓盈利侧 → 利润迁移 → 结构重建”的再平衡
- **AND** 更新 `P_ref = P_t`

#### Scenario: 微量仓位处理
- **WHEN** 交易数量或名义价值低于最小阈值
- **THEN** 忽略该笔交易并清理对应方向的微量仓位
- **AND** 阈值可通过 `min_trade_qty` 与 `min_trade_notional` 配置（默认随初始资金缩放）

### Requirement: 退出机制
策略 SHALL 提供退出模式，触发后分阶段减仓直至仓位基本归零。

#### Scenario: 触发退出并分阶段减仓
- **WHEN** 触发退出条件（如 `sigma_eff^2 < k * MES^2` 持续 M 次（默认 k=0.01, M=10）且至少完成一次再平衡，或 `E_t > E_max`）
- **THEN** 进入退出模式并按 `eta` 比例逐步减仓
- **AND** 当 `qL + qS < epsilon` 时退出完成
