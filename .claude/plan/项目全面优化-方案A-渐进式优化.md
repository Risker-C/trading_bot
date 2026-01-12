# 项目全面优化 - 方案A：渐进式优化

> **状态**: 已批准 | **开始日期**: 2026-01-12 | **预计周期**: 3周

## 执行摘要

**优化目标**：
- 性能提升30%+（响应时间、内存占用、API成本）
- 代码质量达标（类型提示、测试覆盖率>80%）
- 配置管理优化（可视化、热重载、易维护）

**优化范围**：
1. 核心交易模块（bot.py, trader.py）
2. AI分析层（claude_analyzer.py, ml_predictor.py）
3. 数据库与存储（trading_bot.db）
4. 配置与监控（config.py, Dashboard）

**风险控制**：每个阶段都有特性开关，可快速回滚

---

## 整体时间线

```
Week 1: 基础设施建设
├─ 后端：Phase 0-1（指标+配置拆分）
└─ 前端：阶段1（数据建模+API集成）

Week 2: 核心功能开发
├─ 后端：Phase 2-3（ML优化+DB优化）
└─ 前端：阶段2-3（配置编辑器+策略控制台）

Week 3: 质量保障
├─ 后端：Phase 4-5（AI异步化+测试覆盖）
└─ 前端：集成测试+用户验证
```

---

## 后端实施计划（Codex）

### Phase 0: 基线指标与安全护栏（Day 1-2）

**目标**：建立性能基线，添加特性开关

**关键任务**：
- 添加时序指标和内存快照
- 添加特性开关（ASYNC_AI_ENABLED, DB_BATCH_WRITES_ENABLED, ML_FORCE_LITE, CONFIG_SPLIT_ENABLED）

**文件修改**：
- `bot.py`: 包装AI/ML调用，添加延迟指标
- `logger_utils.py`: 添加轻量级指标日志器
- `config.py`: 添加特性开关

**验收标准**：
- ✅ 每次迭代记录延迟指标
- ✅ 特性开关可正常切换
- ✅ 无行为变更

---

### Phase 1: 配置拆分（Day 3-5）

**目标**：将config.py拆分为模块化配置，保持向后兼容

**关键任务**：
- 创建config/目录结构
- 实现向后兼容的shim层

**文件结构**：
```
config/
├── __init__.py       # 加载默认值，导出所有公共符号
├── runtime.py        # 间隔、开关、超时
├── ml.py             # ML标志、模型路径、阈值
├── db.py             # DB_PATH、日志选项
├── ai.py             # Claude设置、预算、超时
├── strategies.py     # ENABLE_STRATEGIES和策略参数
└── paths.py          # LOG_DIR、MODEL_DIR等
```

**兼容性**：
- config.py成为thin shim，从config/导入
- 保留所有遗留名称和默认值

**验收标准**：
- ✅ 所有模块导入config无需修改
- ✅ 配置值与原config.py一致
- ✅ 单元测试验证配置一致性

---

### Phase 2: ML轻量化（Day 6-8）

**目标**：强制启用ml_predictor_lite，降低内存占用60%

**关键任务**：
- 生产环境强制使用轻量级预测器
- 实现模型卸载策略

**文件修改**：
- `bot.py`: ML_FORCE_LITE启用时使用get_ml_predictor_lite()
- `ml_predictor.py`: 标记为遗留路径，添加警告
- `ml_predictor_lite.py`: 添加空闲卸载策略
- `config/ml.py`: 添加ML_FORCE_LITE, ML_UNLOAD_AFTER_IDLE_SECONDS

**验收标准**：
- ✅ 内存占用降低60%
- ✅ 预测准确率不下降
- ✅ 模型加载/卸载正常

---

### Phase 3: 数据库优化（Day 9-12）

**目标**：添加索引，实现批量写入

**关键任务**：
- 为高频查询字段添加索引
- 实现批量插入API

**文件修改**：
- `logger_utils.py`:
  - _init_db(): 创建索引（trades.created_at, trades.strategy, trades.symbol, signals.created_at, signals.strategy）
  - 添加log_trades_batch()和log_signals_batch()
  - 实现内存缓冲+定期刷新
- `bot.py/trader.py`: 使用批量日志API
- `docs/database_standards.md`: 更新索引列表

**验收标准**：
- ✅ 查询速度提升30%+
- ✅ 写入延迟降低
- ✅ 数据完整性验证通过

---

### Phase 4: AI异步化（Day 13-16）

**目标**：AI调用异步化，避免阻塞交易链路

**关键任务**：
- 实现有界执行器
- 超时降级机制

**文件修改**：
- `bot.py`:
  - 引入AIExecutor（ThreadPoolExecutor + 有界队列）
  - 使用futures + timeout
- `claude_analyzer.py`: 添加analyze_async包装器
- `claude_policy_analyzer.py`: 异步入口
- `config/ai.py`: ASYNC_AI_ENABLED, AI_TIMEOUT_SECONDS, AI_MAX_INFLIGHT

**验收标准**：
- ✅ 交易执行不被AI阻塞
- ✅ 超时降级正常工作
- ✅ 无交易决策偏差

---

### Phase 5: 类型提示与测试（Day 17-21）

**目标**：添加类型提示，测试覆盖率达到80%

**关键任务**：
- 核心模块添加类型提示
- 编写单元测试和集成测试

**文件修改**：
- `bot.py, trader.py, logger_utils.py`: 类型提示
- `claude_analyzer.py, ml_predictor*.py`: 输入/输出类型
- `tests/`:
  - test_config_split.py
  - test_ml_lite.py
  - test_db_indexes.py
  - test_ai_async.py

**验收标准**：
- ✅ 核心路径测试覆盖率>80%
- ✅ 类型检查通过
- ✅ 所有测试通过

---

## 前端实施计划（Gemini）

### 阶段1: 基础设施与数据建模（Week 1）

**目标**：建立配置的"真值来源"

**后端任务**：
- 引入pydantic定义ConfigSchema
- 实现ConfigManager类（from_py_file, to_json, from_json）

**前端任务**：
- 在types/config.ts定义TypeScript接口
- 配置React Query用于配置数据获取

**API接口**：
```
GET  /api/config          # 获取当前配置
PUT  /api/config          # 更新配置
POST /api/config/validate # 实时验证
GET  /api/config/history  # 配置历史
GET  /api/strategies/status # 策略状态
```

**验收标准**：
- ✅ Pydantic Schema定义完整
- ✅ TypeScript接口同步
- ✅ API接口可正常调用

---

### 阶段2: 配置编辑器UI（Week 1.5-2）

**目标**：提供表单化操作界面

**组件开发**：
- ConfigForm: 顶级容器（react-hook-form）
- ParameterField: 数值类（Slider）、开关类（Switch）
- ValidationBadge: 实时显示配置状态

**页面结构**：`/dashboard/settings`
```
├── General（交易所API、运行模式）
├── Risk Management（杠杆、止损、Kelly公式）
├── Strategies（Master Switch + 策略列表）
└── AI & ML（Claude开关、ML阈值）
```

**分级实现**：
- 基础视图：核心开关、仓位、止损
- 专家模式：ML阈值、ATR倍数（折叠栏）

**验收标准**：
- ✅ 配置编辑器UI完整
- ✅ 实时验证正常工作
- ✅ 参数分级清晰

---

### 阶段3: 策略控制台与热重载（Week 2.5）

**目标**：实现策略一键切换与零停机更新

**热重载机制**：
- 后端：文件监控/API信号 → StrategyManager重新初始化
- 前端：WebSocket推送 → UI实时更新

**策略仪表盘**：
- 显示每个策略的运行状态
- 今日收益率
- 一键开关

**用户交互流程**：
1. 用户调整参数 → 前端Zod校验 + 后端/validate
2. 保存修改 → PUT /api/config → 热重载
3. Toast提示 → WebSocket推送 → UI更新

**验收标准**：
- ✅ 热重载无需重启
- ✅ 策略切换实时生效
- ✅ 配置历史可回滚

---

## 关键里程碑

**M1 (Day 5)**：配置拆分完成，前后端数据模型对齐
- 后端：config/目录结构建立，向后兼容
- 前端：ConfigSchema定义，API集成完成

**M2 (Day 12)**：性能优化完成，配置UI可用
- 后端：ML轻量化+DB索引生效
- 前端：配置编辑器上线，实时验证

**M3 (Day 21)**：全面优化完成，质量达标
- 后端：AI异步化+测试覆盖>80%
- 前端：策略控制台+热重载机制

---

## 测试策略

### 单元测试
- 配置拆分一致性测试
- ML强制启用测试
- DB索引验证测试
- AI异步超时测试

### 集成测试
- 端到端影子模式测试
- DB批量写入负载测试
- 配置热重载测试

### 回归测试
- AI异步前后决策对比
- 配置导入兼容性测试

---

## 风险控制与回滚

**特性开关**：
- ASYNC_AI_ENABLED: AI异步化开关
- DB_BATCH_WRITES_ENABLED: 批量写入开关
- ML_FORCE_LITE: ML轻量化开关
- CONFIG_SPLIT_ENABLED: 配置拆分开关

**回滚策略**：
- 每个阶段前打release tag
- 特性开关可快速禁用
- config.py shim保证向后兼容

**监控指标**：
- 响应时间（目标：↓30%）
- 内存占用（目标：↓60%）
- API成本（目标：↓20%）
- 测试覆盖率（目标：>80%）

---

## 技术约束

**性能**：批量写入和异步AI不增加内存
**安全**：不记录敏感信息，清理API token
**可扩展性**：异步执行器避免无界队列
**兼容性**：config.py shim保证向后兼容

---

## 相关文档

- Codex后端详细规划: `docs/phase3_backend_plan.md`
- Gemini前端详细规划: 见本文档前端部分
- 数据库规范: `docs/database_standards.md`
- 配置管理规范: 待创建

---

**批准人**: 用户
**批准日期**: 2026-01-12
**执行状态**: 准备开始实施
