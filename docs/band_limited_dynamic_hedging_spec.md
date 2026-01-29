# Band‑Limited Dynamic Hedging with Graceful Exit
版本：v1.0

## 1. 策略总体定义（Overview）

**定位**
- 非方向性、波动驱动、摩擦感知
- 离散再平衡 + 明确退出机制

**核心目标**
- 在真实交易摩擦存在时，捕获结构性波动收益
- 控制风险暴露的线性增长
- 当结构失效时可控退出

**非目标**
- 不预测趋势
- 不做高频连续做市
- 不追求极端收益

---

## 2. 状态定义（State）

```
State S_t =
(
  P_t,        # 当前价格
  P_ref,      # 上一次再平衡参考价
  qL, pL,     # 多头数量 & 均价
  qS, pS,     # 空头数量 & 均价
  mode        # Active | Pause | Exit
)
```

---

## 3. 参数（最小集）

```
f           # 单边手续费率
MES         # 最小有效操作尺度 (≈ k * f, k ∈ [6,10])
alpha       # 利润迁移比例
E_max       # 最大可用风险资本
tau_max     # 最大允许再平衡间隔
```

Exit 专用参数：
```
MES_exit = δ * MES     (δ ∈ [0.5, 1])
eta       ∈ [0.2, 0.4] # 单次减仓比例
```

---

## 4. 主模型：状态转移与递推

### 4.1 触发条件（No‑Trade Band）

设：
```
ΔP_t = P_t - P_ref
```

- 若 `|ΔP_t| < MES`：不交易
- 若 `|ΔP_t| >= MES`：触发一次再平衡

### 4.2 单次再平衡（价格上涨情形，下降对称）

**浮动盈亏**
```
Π^L = qL * (P_t - pL)
Π^S = qS * (pS - P_t)
```

**兑现比例**
```
Π = β * Π^L   (通常 β=1 表示全平盈利侧)
qL ← (1-β) * qL
```

**利润迁移**
```
Π_loss  = alpha * Π
Π_new   = (1-alpha) * Π
```

**修复亏损侧（空头减仓）**
```
ΔqS = Π_loss / P_t
qS  ← qS - ΔqS
```

**结构重建（双向等额）**
```
Δq  = Π_new / (2 * P_t)
qL ← qL + Δq
qS ← qS + Δq
```

**更新均价**
```
pL ← (qL_old*pL_old + Δq*P_t) / qL
pS ← (qS_old*pS_old + Δq*P_t) / qS
```

**更新参考价**
```
P_ref ← P_t
```

---

## 5. 长期期望收益边界（摘要形式）

假设 `dX_t = μ dt + σ dW_t`，再平衡触发为 `|X_t-X*|>=MES`。

触发次数期望：
```
E[N_T] ≈ (σ^2 / MES^2) * T
```

单次净期望：
```
E[ΔR] = c1 * MES - c2 * f
```

长期期望：
```
E[R_T] = σ^2 T * (c1/MES - c2 f / MES^2)
```

结论：
```
0 <= E[R_T] <= C * (σ^2 / MES)
```
- 上界随波动率增长，与趋势无关
- MES 过小 → 期望为负
- MES 与摩擦匹配 → 可存活

---

## 6. 退出机制（Exit）

### 6.1 退出条件（结构性失效）

**条件一：摩擦–波动失衡**
```
σ_eff^2 < γ1 * MES * f   （持续 K 次）
```

**条件二：风险资本上限**
```
E_t = |qL - qS| * P_t  > γ2 * E_max
```

**条件三：再平衡冻结**
```
E[τ] > tau_max
```

### 6.2 模式转移规则

```
Active → Pause:   C3=1 且 C1=0 且 C2=0
Active/Pause → Exit: C1=1 或 C2=1
Pause → Active:  C1=C2=C3=0
```

---

## 7. 优雅退出路径（分阶段减仓）

**冻结退出参考价**
```
P_ref_exit = P_t
```

**退出尺度**
```
MES_exit = δ * MES
```

**退出触发**
```
若 |P_t - P_ref_exit| >= MES_exit：
    qL ← (1-eta)*qL
    qS ← (1-eta)*qS
    P_ref_exit ← P_t
```

**终止条件**
```
qL + qS < ε  → 完全退出
```

---

## 8. Exit 最坏摩擦上界

假设：
- 初始总仓位 `Q0 = qL + qS`
- 每次减仓比例 `eta`

退出次数上界：
```
N ≤ log(ε / Q0) / log(1-eta)
```

最坏摩擦成本上界：
```
C_exit_max ≤ (2 f Q0) / eta
```

---

## 9. 状态机（UML + 表）

### 9.1 UML（ASCII）

```
        ┌──────────────┐
        │   Active     │
        │  再平衡运行  │
        └──────┬───────┘
               │  τ > τ_max
               ▼
        ┌──────────────┐
        │   Pause      │
        │ 等待环境改善 │
        └──────┬───────┘
               │
   ┌───────────┼───────────┐
   │           │           │
   ▼           ▼           ▼
Exit(σ失衡) Exit(资本) Exit(人工)
   │
   ▼
┌──────────────┐
│     Exit     │
│ 分阶段减仓   │
└──────┬───────┘
       ▼
   Fully Flat
```

### 9.2 状态转移表

| 当前状态 | 条件 | 下一状态 |
| --- | --- | --- |
| Active | 正常 | Active |
| Active | τ > τ_max | Pause |
| Active | σ_eff^2 < 阈值 | Exit |
| Active | E_t > 上限 | Exit |
| Pause | 条件恢复 | Active |
| Pause | σ/E 失效 | Exit |
| Exit | qL+qS≈0 | End |

---

## 10. 伪代码（主循环 + 再平衡 + Exit）

```
while running:
    update P_t
    ΔP = P_t - P_ref

    update τ, σ_eff^2, E_t
    mode = update_mode(mode, σ_eff^2, τ, E_t)

    if mode == ACTIVE:
        if abs(ΔP) >= MES:
            rebalance()
            P_ref = P_t

    elif mode == PAUSE:
        continue

    elif mode == EXIT:
        graceful_exit()
        if qL + qS < ε:
            break
```

**rebalance()**
```
if P_t > P_ref:
    profit = qL * (P_t - pL)
    realized = profit
    loss_part = alpha * realized
    rebuild_part = (1 - alpha) * realized

    qL = 0
    reduce_S = loss_part / P_t
    qS = max(qS - reduce_S, 0)

else:
    # 对称逻辑

delta_q = rebuild_part / (2 * P_t)
qL += delta_q
qS += delta_q
update pL, pS
```

**graceful_exit()**
```
if not P_ref_exit:
    P_ref_exit = P_t

if abs(P_t - P_ref_exit) >= MES_exit:
    qL = (1 - eta) * qL
    qS = (1 - eta) * qS
    P_ref_exit = P_t
```

---

## 11. AI 可识别规范（JSON）

```
{
  "strategy": {
    "name": "BandLimitedDynamicHedging",
    "type": "event_driven_non_directional",
    "version": "1.0"
  },
  "state": {
    "price": "P_t",
    "reference_price": "P_ref",
    "long_position": { "quantity": "qL", "average_price": "pL" },
    "short_position": { "quantity": "qS", "average_price": "pS" },
    "mode": ["ACTIVE", "PAUSE", "EXIT"]
  },
  "parameters": {
    "transaction_fee": "f",
    "MES": "k * f",
    "profit_transfer_ratio": "alpha",
    "max_risk_capital": "E_max",
    "max_rebalance_interval": "tau_max",
    "exit": { "MES_exit_ratio": "delta", "decrease_ratio": "eta" }
  },
  "triggers": {
    "rebalance": "abs(P_t - P_ref) >= MES",
    "pause": "expected_rebalance_interval > tau_max",
    "exit": [
      "effective_volatility < MES * transaction_fee",
      "risk_exposure > max_risk_capital"
    ]
  },
  "actions": {
    "rebalance": [
      "realize_profit_on_winning_side",
      "transfer_profit_to_losing_side",
      "rebuild_symmetric_positions",
      "update_reference_price"
    ],
    "pause": [ "halt_new_rebalancing", "monitor_market_conditions" ],
    "exit": [
      "freeze_reference_price",
      "reduce_both_positions_by_eta_when_price_moves_by_MES_exit",
      "terminate_when_positions_near_zero"
    ]
  },
  "invariants": [
    "no_direction_prediction",
    "no_trade_within_MES_band",
    "risk_exposure_growth_is_linear",
    "exit_cost_is_bounded"
  ]
}
```

---

## 12. AI 状态机（YAML）

```
states:
  ACTIVE:
    description: Normal operation with band-limited rebalancing
    on:
      price_update:
        if: "abs(P_t - P_ref) >= MES"
        do: rebalance
      monitor:
        if: "rebalance_interval > tau_max"
        transition_to: PAUSE
        if_exit:
          condition: "effective_volatility < MES * fee or risk_exposure > E_max"
          transition_to: EXIT

  PAUSE:
    description: Strategy frozen, no new risk added
    on:
      monitor:
        if: "market_conditions_recover"
        transition_to: ACTIVE
        if_exit:
          condition: "effective_volatility < MES * fee or risk_exposure > E_max"
          transition_to: EXIT

  EXIT:
    description: Graceful exit using band-limited reduction
    on:
      price_update:
        if: "abs(P_t - P_ref_exit) >= MES_exit"
        do: reduce_positions
      terminate:
        if: "qL + qS < epsilon"
        transition_to: TERMINATED

actions:
  rebalance:
    - realize_profit
    - transfer_profit
    - rebuild_positions
    - update_reference_price
  reduce_positions:
    - qL: "qL * (1 - eta)"
    - qS: "qS * (1 - eta)"
```

---

## 13. 硬约束（不可违反）

1) MES 区间内禁止交易
2) 不引入方向性偏差
3) 退出不基于价格止损
4) 退出也遵循 band‑limited 原则
5) Exit 成本必须有明确上界
