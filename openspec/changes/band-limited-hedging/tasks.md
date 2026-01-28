# Tasks: band-limited-hedging

## 1. Spec & Validation
- [x] 补齐变更 spec：`openspec/changes/band-limited-hedging/specs/band-limited-hedging/spec.md`
- [x] 运行 `openspec validate band-limited-hedging --strict --no-interactive`

## 2. Backend (回测)
- [x] 在 `strategies/strategies.py` 新增 `BandLimitedHedgingStrategy` 并实现 `analyze()`
- [x] 注册到 `STRATEGY_MAP`，名称 `band_limited_hedging`
- [x] 策略内部维护 `P_ref`, `qL/pL`, `qS/pS`, `mode`（Active/Pause/Exit）
- [x] 在 `backtest/engine.py` 增加该策略的双向持仓执行路径（不影响现有单向/多策略逻辑）
- [x] 交易记录 side/action 正确落库，并保持与现有 UI 兼容

## 3. API/参数
- [x] 在 `apps/api/models/backtest.py` 对 `strategy_params` 执行 `MES/alpha/E_max` 校验
- [x] 回测请求中支持传入/保存该策略参数

## 4. Frontend
- [x] `StrategyMultiSelector`/`WeightConfigList` 添加 `band_limited_hedging` 文案
- [x] 在回测配置页面新增该策略参数表单（MES/alpha/E_max）与校验提示
- [x] 单策略模式下将参数写入 `strategyParams` 并随请求发送

## 5. Tests (最小集)
- [x] 添加策略 analyze 的基础单测（MES 内 hold、MES 外触发）
- [x] 回测引擎最小集成测试（双向持仓、交易记录）

## 6. 完成确认
- [x] 更新本 tasks.md 勾选完成项
