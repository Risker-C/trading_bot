# Band‑Limited Dynamic Hedging（含本金维持与动态阈值）白皮书
版本：v1.1（结合 2026-01-28 对话记录与当前实现）

> 本文档基于 `chat-export (3).md` 中的数学模型与当前代码实现（`strategies/strategies.py`、`apps/api/models/backtest.py`），整理为可落地的策略白皮书与伪代码。

---

## 1. 策略定位

**核心思想**
- 双向持仓（多 + 空）降低单边暴露
- 只有当价格偏移超过 MES（最小有效操作尺度）才再平衡
- 盈利侧平仓 → 利润迁移 → 结构重建
- 允许“真空区”存在，但通过 MES 控制增长

**核心目标**
- 在存在交易摩擦（手续费、资金费）的现实市场中，通过波动获取结构性收益
- 不依赖方向预测，不依赖回撤假设
- 在结构失效时可控退出

**非目标**
- 不做趋势预测
- 不做连续做市
- 不追求极端收益

---

## 2. 状态定义（State）

在任意时刻 $t$：

```
S_t = (
  P_t,        # 当前价格
  P_ref,      # 上一次再平衡参考价
  qL, pL,     # 多头数量 & 均价
  qS, pS,     # 空头数量 & 均价
  mode        # Active | Pause | Exit
)
```

---

## 3. 参数定义（含实现扩展）

**核心参数**
```
f           # 单边手续费率
MES         # 最小有效操作尺度（默认 9 * fee_rate）
alpha       # 利润迁移比例 (0,1)
E_max       # 最大风险资本
```

**实现扩展（对话后新增）**
```
base_position_ratio        # 本金维持比例（默认 0.95）
min_rebalance_profit       # 固定盈利阈值（默认 0）
min_rebalance_profit_ratio # 动态盈利阈值倍数（默认 1.0）
min_trade_qty              # 最小成交数量
min_trade_notional         # 最小成交名义价值

# 退出控制
eta              # Exit 单次减仓比例（默认 0.2）
MES_exit_ratio   # Exit 触发尺度比例（默认 0.7）
tau_max          # 再平衡冻结阈值（可选）
```

**动态盈利阈值（实现版）**
```
min_profit = max(
  min_rebalance_profit,
  qty * price * fee_rate * min_rebalance_profit_ratio
)
```

---

## 4. 触发条件（No‑Trade Band）

```
ΔP = |P_t - P_ref| / P_ref
```
- 若 `ΔP < MES`：不交易
- 若 `ΔP >= MES`：进入“再平衡判定”

---

## 5. 再平衡逻辑（价格上涨示例）

1) 计算盈利侧净收益（扣手续费）
```
net_profit = (P_t - pL) * qL - fee(qL, P_t)
```

2) 若 `net_profit < min_profit`：跳过再平衡

3) 若满足阈值，执行：
- 平仓盈利侧（全平，β=1）
- 利润迁移：`loss_part = alpha * net_profit`
- 结构重建：`rebuild_part = (1 - alpha) * net_profit`
- 重建数量：
  `Δq = rebuild_part / (2 * P_t)`

4) 本金维持（实现新增）
```
base_qty = (initial_capital * base_position_ratio / 2) / P_t
if qL < base_qty: 补多
if qS < base_qty: 补空
```

---

## 6. 退出机制（Exit）

**触发条件（实现版）**
- 低波动退出：`sigma_eff^2 < k * MES * fee_rate` 持续 N 次
- 风险资本退出：`|qL - qS| * P_t > E_max`
- 再平衡冻结（可选）：`τ > tau_max` → Pause

**Exit 行为**（仍遵循 band-limited）
```
MES_exit = MES * MES_exit_ratio
若 |P_t - P_ref_exit|/P_ref_exit >= MES_exit：
  qL = (1 - eta) * qL
  qS = (1 - eta) * qS
```

---

## 7. 关键结论（来自对话记录）

1) **MES 是摩擦过滤器**，过小必然被手续费吃掉。
2) 策略收益来源是“波动”而非“方向”。
3) 空窗期出现的主要原因是“盈利阈值过高”。
4) 引入 **本金维持结构** 后，仓位不会因重复再平衡而缩小至 0。

---

## 8. 最优 MES（批量回测结果）

基于指定一组 session 对比结果：
- 最佳收益率出现在 **MES = 0.009**
- 作为默认值已同步到后端与前端

---

# 9. 对应实现伪代码（与当前代码对齐）

## 9.1 主循环

```
while running:
  P_t = last_close
  if P_ref is None:
    init_dual_position()
    P_ref = P_t
    last_rebalance_ts = now
    continue

  update_mode()  # Active / Pause / Exit

  if mode == EXIT:
    graceful_exit()
    return

  if mode == PAUSE:
    if |P_t - P_ref|/P_ref >= MES:
      mode = ACTIVE
    continue

  if |P_t - P_ref|/P_ref < MES:
    return  # no trade

  if P_t >= P_ref:
    actions = rebalance_up(P_t)
  else:
    actions = rebalance_down(P_t)

  if actions empty:
    return  # skip, profit too small
```

## 9.2 再平衡（上涨）

```
rebalance_up(price):
  if qL == 0: return []

  net_profit = (price - pL) * qL - fee(qL, price)
  min_profit = max(min_rebalance_profit, qL * price * fee_rate * ratio)
  if net_profit < min_profit: return []

  close long (full)
  loss_part = alpha * net_profit
  rebuild_part = net_profit - loss_part

  reduce short by loss_part/price
  open long/short with rebuild_part/(2*price)

  maintain_base_position(price)
  P_ref = price
  last_rebalance_ts = now
  return actions
```

## 9.3 本金维持

```
maintain_base_position(price):
  base_qty = (initial_capital * base_position_ratio / 2) / price
  if qL < base_qty: open long (base_qty - qL)
  if qS < base_qty: open short (base_qty - qS)
```

## 9.4 Exit（优雅退出）

```
graceful_exit():
  if exit_ref is None: exit_ref = price
  if |price - exit_ref|/exit_ref < MES_exit: return []

  reduce qL and qS by eta
  if qL + qS <= epsilon: mode = PAUSE
  exit_ref = price
```

---

## 10. 适配清单（实现一致性）

- 后端默认 MES：`9 * fee_rate`
- 前端默认 MES：`0.009`
- 动态阈值：`qty * price * fee_rate * ratio`
- 本金维持：`base_position_ratio = 0.95`
- Exit：分阶段减仓 + MES_exit 触发

---

## 11. 风险提示

- 更小 MES → 交易更频繁 → 手续费占比上升
- 动态阈值过高 → 容易出现空窗期
- 本金维持会增加交易笔数，但提升结构稳定性

---

## 12. 推荐默认参数（当前版本）

```
MES = 0.009
alpha = 0.5
E_max = initial_capital
base_position_ratio = 0.95
min_rebalance_profit = 0.0
min_rebalance_profit_ratio = 1.0
```

