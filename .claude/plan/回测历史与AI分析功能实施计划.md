# 回测历史与AI分析功能实施计划

> **状态**: 待批准 | **创建日期**: 2026-01-19 | **预计周期**: 4周

## 执行摘要

**功能目标**：
1. **回测历史查看功能**：支持>1000条历史记录的高性能检索、高级筛选、详情查看
2. **AI分析功能**：单次回测分析、批量对比分析、全自动策略优化（含审批流程）

**技术方案**：
- 后端：FastAPI + SQLite（摘要表 + 索引优化 + 分页）
- 前端：Next.js 嵌套路由 + TanStack Table + React Virtual
- AI：复用现有 Claude Analyzer，增加回测专用 prompt

**实施策略**：渐进式三阶段（P0/P1/P2）

---

## 整体架构

### 后端架构（Codex 设计）

**核心设计决策**：
- ✅ 使用"摘要表"（`backtest_session_summaries`）作为历史列表读模型，避免频繁 join
- ✅ 采用 cursor pagination（`created_at + id`）保证高并发列表稳定性
- ✅ AI 分析结果落库（`backtest_ai_reports`），支持审计和复现
- ✅ 审批与审计独立表管理（`backtest_change_requests` + `backtest_audit_logs`）

**新增数据表**：
1. `backtest_session_summaries` - 扁平化的会话摘要（sessions + metrics）
2. `backtest_ai_reports` - AI 分析结果存储
3. `backtest_change_requests` - 策略变更审批流程
4. `backtest_audit_logs` - 操作审计日志

**新增 API 端点**：
- `GET /api/backtests/sessions` - 历史列表（分页 + 筛选 + 排序）
- `GET /api/backtests/sessions/{id}/detail` - 会话详情聚合
- `POST /api/backtests/sessions/{id}/ai-analysis` - 触发 AI 分析
- `GET /api/backtests/sessions/{id}/ai-analysis` - 获取分析结果
- `POST /api/backtests/ai-analysis/compare` - 批量对比分析
- `POST /api/backtests/change-requests` - 创建变更请求
- `POST /api/backtests/change-requests/{id}/approve` - 审批变更
- `POST /api/backtests/change-requests/{id}/apply` - 应用变更

### 前端架构（Gemini 设计）

**路由设计**：
```
/backtest (layout.tsx - 二级导航)
├── /new (page.tsx) - 新建回测页面（已存在，需优化）
├── /history (page.tsx) - 历史列表页（新增）
├── /history/[id] (page.tsx) - 回测详情页（新增）
└── /compare (page.tsx) - AI 批量对比页（新增）
```

**核心组件**：
1. `BacktestVirtualTable` - 虚拟滚动表格（@tanstack/react-virtual）
2. `FilterBar` + `AdvancedFilterDrawer` - 高级筛选器
3. `AIReportCard` - AI 分析报告展示
4. `SyncApprovalModal` - 配置变更审批界面（Diff 视图）
5. `MetricCell` - Sparkline 小型盈亏曲线预览

**状态管理**：
- Zustand：`useBacktestStore`（扩展 `compareList` 和 `lastFilter`）
- React Query：缓存列表和详情数据，支持预取

---

## 分阶段实施计划

### P0：历史查看基础（1-2周）

#### 后端任务
- [ ] **数据库迁移**：创建 `backtest_session_summaries` 表及索引
- [ ] **Repository 层**：实现 `SummaryRepository.upsert_from_session()`
- [ ] **更新回测流程**：回测完成时自动更新摘要表
- [ ] **列表 API**：实现 `GET /api/backtests/sessions`（cursor 分页 + 筛选 + 排序）
- [ ] **详情 API**：实现 `GET /api/backtests/sessions/{id}/detail`（聚合端点）
- [ ] **单元测试**：筛选、分页、排序逻辑测试

#### 前端任务
- [ ] **路由重构**：迁移 `backtest/page.tsx` → `backtest/new/page.tsx`
- [ ] **历史列表页**：实现 `backtest/history/page.tsx`
  - 虚拟滚动表格（@tanstack/react-virtual）
  - 基础筛选器（日期范围、策略名称）
  - 分页加载
- [ ] **详情页**：实现 `backtest/history/[id]/page.tsx`
  - 复用现有 KLineChart 组件
  - 展示交易明细和指标卡片
- [ ] **导航菜单**：在 DashboardLayout 中添加"回测历史"入口

#### 验收标准
- ✅ 用户可以查看历史回测列表（支持 1000+ 条记录流畅滚动）
- ✅ 支持按时间、策略名称筛选
- ✅ 点击列表项可查看详情（K线图 + 交易明细）
- ✅ 列表加载性能 <500ms（1000 条记录）

---

### P1：AI 分析功能（1周）

#### 后端任务
- [ ] **数据库迁移**：创建 `backtest_ai_reports` 表及索引
- [ ] **AI 输入聚合**：实现特征提取（metrics + 紧凑交易统计）
- [ ] **AI Repository**：实现报告持久化和检索
- [ ] **AI 分析 API**：
  - `POST /api/backtests/sessions/{id}/ai-analysis`（触发分析）
  - `GET /api/backtests/sessions/{id}/ai-analysis`（获取结果）
- [ ] **批量对比 API**：`POST /api/backtests/ai-analysis/compare`
- [ ] **安全防护**：添加速率限制和 payload 大小保护

#### 前端任务
- [ ] **高级筛选器**：实现 `AdvancedFilterDrawer`
  - 收益率、夏普比率、最大回撤、胜率滑块
  - 多条件组合筛选
- [ ] **AI 分析面板**：在详情页添加 `AIAnalysisSidebar`
  - 触发分析按钮
  - Markdown 渲染 AI 报告
  - 加载状态和错误处理
- [ ] **Sparkline 预览**：在列表中添加 `MetricCell`（小型盈亏曲线）
- [ ] **批量选择**：列表支持多选，启用"对比分析"按钮

#### 验收标准
- ✅ 用户可以对单次回测触发 AI 分析
- ✅ AI 报告展示策略优劣势和优化建议
- ✅ 支持选择 2-5 个回测进行批量对比
- ✅ AI 分析结果可持久化和重复查看

---

### P2：全自动优化（2周）

#### 后端任务
- [ ] **数据库迁移**：创建 `backtest_change_requests` 和 `backtest_audit_logs` 表
- [ ] **RBAC 实现**：角色权限控制（admin/approver/apply）
- [ ] **变更请求 API**：
  - `POST /api/backtests/change-requests`（创建变更）
  - `POST /api/backtests/change-requests/{id}/approve`（审批）
  - `POST /api/backtests/change-requests/{id}/reject`（拒绝）
  - `POST /api/backtests/change-requests/{id}/apply`（应用）
- [ ] **审计日志**：所有状态变更自动记录
- [ ] **配置应用**：集成受控的配置更新和重启流程
- [ ] **回滚机制**：文档化回滚操作指南

#### 前端任务
- [ ] **对比页面**：实现 `backtest/compare/page.tsx`
  - 多维雷达图对比
  - 参数差异表格
  - AI 批量分析报告
- [ ] **审批界面**：实现 `SyncApprovalModal`
  - Diff 视图（当前配置 vs AI 建议）
  - 二次确认机制
  - 审批流程状态展示
- [ ] **变更历史**：添加变更请求列表页
  - 展示所有变更记录
  - 状态筛选（pending/approved/rejected/applied）
  - 审计日志查看

#### 验收标准
- ✅ AI 可以生成参数优化建议
- ✅ 变更需要经过审批流程（创建 → 审批 → 应用）
- ✅ 配置变更前展示 Diff 对比
- ✅ 所有操作有完整审计日志
- ✅ 支持变更回滚

---

## 数据库设计

### 新增表结构

#### backtest_session_summaries（摘要表）
```sql
CREATE TABLE backtest_session_summaries (
  session_id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  status TEXT NOT NULL,
  symbol TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  start_ts INTEGER NOT NULL,
  end_ts INTEGER NOT NULL,
  strategy_name TEXT NOT NULL,
  strategy_params TEXT,
  total_trades INTEGER,
  win_rate REAL,
  total_return REAL,
  max_drawdown REAL,
  sharpe REAL
);

CREATE INDEX idx_summary_created_at ON backtest_session_summaries(created_at);
CREATE INDEX idx_summary_strategy ON backtest_session_summaries(strategy_name);
CREATE INDEX idx_summary_return ON backtest_session_summaries(total_return);
CREATE INDEX idx_summary_sharpe ON backtest_session_summaries(sharpe);
CREATE INDEX idx_summary_drawdown ON backtest_session_summaries(max_drawdown);
CREATE INDEX idx_summary_winrate ON backtest_session_summaries(win_rate);
```

#### backtest_ai_reports（AI 分析结果）
```sql
CREATE TABLE backtest_ai_reports (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  model_name TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_digest TEXT NOT NULL,
  summary TEXT NOT NULL,
  strengths TEXT,
  weaknesses TEXT,
  recommendations TEXT,
  param_suggestions TEXT,
  compare_group_id TEXT,
  FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

CREATE INDEX idx_ai_session ON backtest_ai_reports(session_id);
CREATE INDEX idx_ai_group ON backtest_ai_reports(compare_group_id);
CREATE INDEX idx_ai_created_at ON backtest_ai_reports(created_at);
```

#### backtest_change_requests（变更审批）
```sql
CREATE TABLE backtest_change_requests (
  id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  status TEXT NOT NULL,  -- pending/approved/rejected/applied/failed
  session_id TEXT NOT NULL,
  strategy_name TEXT NOT NULL,
  target_env TEXT NOT NULL,  -- staging/prod
  change_payload TEXT NOT NULL,
  approved_by TEXT,
  approved_at INTEGER,
  applied_by TEXT,
  applied_at INTEGER,
  error_message TEXT,
  FOREIGN KEY (session_id) REFERENCES backtest_sessions(id)
);

CREATE INDEX idx_cr_status ON backtest_change_requests(status);
CREATE INDEX idx_cr_env ON backtest_change_requests(target_env);
CREATE INDEX idx_cr_created_at ON backtest_change_requests(created_at);
```

#### backtest_audit_logs（审计日志）
```sql
CREATE TABLE backtest_audit_logs (
  id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  payload TEXT
);

CREATE INDEX idx_audit_target ON backtest_audit_logs(target_type, target_id);
CREATE INDEX idx_audit_created_at ON backtest_audit_logs(created_at);
```

---

## 关键技术实现

### 后端：Cursor 分页（Codex 设计）
```python
def list_summaries(filters, cursor=None, limit=50, sort_by="created_at", sort_dir="desc"):
    sql = "SELECT * FROM backtest_session_summaries WHERE 1=1"
    params = {}

    # 筛选条件
    if filters.strategy_name:
        sql += " AND strategy_name = :strategy_name"
        params["strategy_name"] = filters.strategy_name
    if filters.total_return_min is not None:
        sql += " AND total_return >= :total_return_min"
        params["total_return_min"] = filters.total_return_min

    # Cursor 分页
    if cursor:
        created_at, session_id = cursor.split(":")
        sql += " AND (created_at, session_id) < (:created_at, :session_id)"
        params.update({"created_at": int(created_at), "session_id": session_id})

    sql += f" ORDER BY {sort_by} {sort_dir}, session_id {sort_dir} LIMIT :limit"
    params["limit"] = limit

    return query(sql, params)
```

### 前端：虚拟滚动表格（Gemini 设计）
```tsx
const rowVirtualizer = useVirtualizer({
  count: data.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 50, // 固定行高
  overscan: 10,
});

return (
  <div ref={parentRef} className="overflow-auto h-[600px]">
    <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
      {rowVirtualizer.getVirtualItems().map((virtualRow) => (
        <div
          key={virtualRow.index}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: `${virtualRow.size}px`,
            transform: `translateY(${virtualRow.start}px)`,
          }}
        >
          <BacktestRowData data={data[virtualRow.index]} />
        </div>
      ))}
    </div>
  </div>
);
```

### 前端：配置 Diff 视图（Gemini 设计）
```tsx
const ConfigDiff = ({ oldConfig, newConfig }) => {
  return (
    <div className="grid grid-cols-2 gap-4 bg-muted p-4 rounded-md">
      <div>
        <h4 className="text-xs font-bold text-red-500">当前配置</h4>
        <pre>{JSON.stringify(oldConfig, null, 2)}</pre>
      </div>
      <div>
        <h4 className="text-xs font-bold text-green-500">AI 建议</h4>
        <pre className="bg-green-500/10">{JSON.stringify(newConfig, null, 2)}</pre>
      </div>
    </div>
  );
};
```

---

## 风险与缓解措施

### 技术风险
| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| SQLite 并发性能 | 高并发下可能锁等待 | 启用 WAL 模式，设置 busy_timeout |
| 虚拟滚动兼容性 | 不同浏览器表现差异 | 使用成熟库（@tanstack/react-virtual），充分测试 |
| AI prompt 注入 | 安全风险 | 输入验证，AI 输出当作不可信数据处理 |

### 业务风险
| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 全自动应用错误配置 | 资金损失 | 强制审批流程，Diff 预览，可回滚 |
| AI 分析不一致 | 决策混乱 | 记录 prompt 版本和输入摘要，支持审计 |
| 历史数据不可复现 | 分析不可靠 | 记录策略版本、代码 hash、手续费假设 |

---

## 依赖安装

### 后端
```bash
# 无需新增依赖，复用现有 FastAPI, SQLite, ccxt, pandas
```

### 前端
```bash
cd apps/dashboard
npm install @tanstack/react-table @tanstack/react-virtual @tanstack/react-query
```

---

## 验收标准总览

### P0 验收
- ✅ 历史列表支持 1000+ 条记录流畅滚动
- ✅ 支持按时间、策略名称筛选
- ✅ 详情页展示完整回测结果

### P1 验收
- ✅ AI 分析功能可用且结果可持久化
- ✅ 支持批量对比分析（2-5 个回测）
- ✅ 高级筛选器支持多维度组合

### P2 验收
- ✅ 变更审批流程完整（创建 → 审批 → 应用）
- ✅ 配置变更前展示 Diff 对比
- ✅ 所有操作有审计日志
- ✅ 支持变更回滚

---

## 后续扩展方向

1. **参数优化引擎**：网格搜索/贝叶斯优化自动寻找最优参数
2. **回测对比可视化**：多维雷达图、参数热力图
3. **策略版本管理**：Git 集成，策略代码版本追踪
4. **分布式回测**：支持并行执行多个回测任务
5. **实时回测**：模拟实盘环境的实时回测

---

**Codex Session ID**: `019bd4f3-f46c-7ed2-91db-ff0d25e48c61`
**Gemini Session ID**: `9a7ce09f-4230-45fb-8403-2d9f0e510cd1`
