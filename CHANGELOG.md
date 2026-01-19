# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - 2026-01-19

#### 回测历史与AI分析功能完整实现

**类型**: 🎉 新功能

**功能概述**:
实现了完整的回测历史管理和AI智能分析系统，包括回测历史查看、AI智能分析和策略优化审批三大核心功能。该系统通过AI分析回测结果，为交易策略优化提供数据驱动的决策支持，并通过审批流程确保生产环境的安全性。采用前后端分离架构，支持大规模数据（>1000条记录）的高效查询和展示。

**修改内容**:

##### 数据库层（4个迁移文件）
- `migrations/001_add_backtest_summaries.sql`: 创建回测摘要表（denormalized read model），包含6个索引优化查询性能
- `migrations/002_add_ai_reports.sql`: 创建AI分析报告存储表，支持分析结果持久化
- `migrations/003_add_change_requests.sql`: 创建变更请求和审计日志表，实现完整审批流程
- `migrations/004_add_composite_indexes.sql`: 添加复合索引优化游标分页性能

##### 后端Repository层（4个新文件）
- `backtest/summary_repository.py`: 回测摘要的CQRS读模型，实现游标分页和SQL注入防护
- `backtest/ai_repository.py`: AI分析报告的持久化存储，支持历史查询
- `backtest/ai_service.py`: AI分析服务，集成Claude API进行智能分析
- `backtest/change_request_repository.py`: 变更请求和审计日志管理

##### 后端API层（3个新路由）
- `apps/api/routes/backtest_history.py`: 回测历史查询API，支持分页、排序、多维度筛选
- `apps/api/routes/backtest_ai.py`: AI分析API，支持单会话分析和多会话对比
- `apps/api/routes/change_requests.py`: 变更请求审批流程API
- `apps/api/main.py`: 注册新增的API路由

##### 前端组件（多个新文件）
- `apps/dashboard/app/backtest/layout.tsx`: 回测模块Tab导航布局
- `apps/dashboard/app/backtest/new/page.tsx`: 新建回测页面（重构）
- `apps/dashboard/app/backtest/history/page.tsx`: 回测历史列表页，支持筛选和分页
- `apps/dashboard/app/backtest/history/[id]/page.tsx`: 回测详情页，包含指标、图表、交易记录和AI分析
- `apps/dashboard/app/backtest/change-requests/page.tsx`: 变更请求管理页面
- `apps/dashboard/components/backtest/AIAnalysisPanel.tsx`: AI分析面板组件，支持自动加载和手动触发

##### 修改的文件
- `backtest/engine.py`: 回测完成后自动更新摘要表
- `apps/dashboard/app/backtest/page.tsx`: 删除（重构为new/page.tsx）

**技术细节**:

##### 核心实现
- **CQRS模式**: 使用denormalized read model优化查询性能，避免JOIN操作
- **游标分页**: 实现稳定的游标分页，支持大规模数据查询
- **SQL注入防护**: 使用白名单验证sort_by参数，防止SQL注入攻击
- **外键约束**: 所有Repository启用外键约束，确保数据完整性
- **复合索引**: 创建(created_at, session_id)和(session_id, created_at)复合索引优化查询
- **错误处理**: AI服务统一抛出异常，API层捕获并返回适当的HTTP状态码
- **WAL模式**: SQLite使用WAL模式提高并发性能

##### 配置项
```python
# AI分析需要设置环境变量
ANTHROPIC_AUTH_TOKEN = "your_api_token"

# 数据库配置
PRAGMA journal_mode=WAL
PRAGMA foreign_keys=ON
PRAGMA busy_timeout=5000
PRAGMA synchronous=NORMAL
```

**测试结果**:
- ✅ 数据库表结构验证: 通过
- ✅ 外键约束测试: 通过
- ✅ 复合索引验证: 通过
- ✅ Summary Repository功能测试: 通过
- ✅ SQL注入防护测试: 通过（成功拦截4种恶意输入）
- ✅ AI Repository功能测试: 通过
- ✅ 游标分页测试: 通过（无数据重复）
- ✅ AI服务错误处理测试: 通过
- ✅ 变更请求Repository测试: 通过
- ✅ 审计日志测试: 通过
- **测试成功率**: 100% (10/10)

**影响范围**:
- 新增回测历史查看功能，不影响现有回测执行流程
- 新增AI分析功能，需要配置ANTHROPIC_AUTH_TOKEN才能使用
- 新增变更请求审批流程，为后续生产环境部署提供安全保障
- 数据库新增4张表和2个复合索引，不影响现有表结构

**使用说明**:

1. **查看回测历史**:
   - 访问 `http://localhost:3000/backtest/history`
   - 支持按策略、时间、性能指标筛选
   - 点击记录查看详情

2. **使用AI分析**:
   - 在回测详情页点击"AI分析"标签
   - 点击"开始分析"触发AI分析
   - 查看优势、劣势、建议和参数优化建议

3. **创建变更请求**:
   - 基于AI分析结果创建变更请求
   - 通过审批流程应用到staging或prod环境

**后续建议**:
- 实现AI分析的后台任务处理，避免阻塞用户请求
- 添加Redis缓存层，缓存热点数据和AI分析结果
- 实现数据归档机制，定期归档历史数据
- 添加前端虚拟滚动，优化大数据量展示性能
- 集成其他AI模型（如GPT-4），提供多模型对比分析

**文档和测试**:
- 新增 `docs/backtest_history_and_ai_analysis.md` 功能说明文档（完整的使用指南、技术实现、故障排查）
- 新增 `scripts/test_backtest_history_and_ai.py` 测试用例（10个测试用例，100%通过率）
- 更新 `CHANGELOG.md` 记录本次修改

---

### Added - 2026-01-17

#### P1/P2 优化实现 - 优化服务真实回测功能

**新增功能**:
- `SQLiteRepository.load_kline_dataset()` - 加载并解压K线数据集
- `SQLiteRepository.get_strategy_version()` - 获取策略版本信息
- 优化服务数据预加载机制，避免重复数据库查询
- 优化任务异常处理，自动更新任务状态为 'failed'
- 优化任务并发控制，防止重复启动

**改进**:
- `BaseStrategy.__init__` 现在接受 `**kwargs` 参数，支持优化参数传递
- 优化结果结构扁平化，`run_id` 和 `param_set_id` 提升到顶层
- `OptimizationService` 使用真实回测替代模拟数据
- API层注入 `BacktestService` 和 `DataService`，支持真实数据获取

**修复**:
- 修复优化服务返回模拟数据的问题（P1）
- 修复 Repository 缺少必要方法的问题（P2）
- 修复策略参数传递导致的 TypeError
- 修复优化结果写入数据库失败的问题
- 修复并发启动优化任务的竞态条件

**文件变更**:
- `backtest/adapters/storage/sqlite_repo.py` - 新增数据加载方法
- `backtest/services/optimization_service.py` - 性能优化和异常处理
- `backtest/services/backtest_service.py` - 修复策略参数传递
- `apps/api/routes/optimization.py` - 服务注入和并发控制
- `strategies/strategies.py` - BaseStrategy 支持 **kwargs
- `backtest/optimization/grid_search.py` - 结果结构扁平化
- `backtest/optimization/genetic.py` - 结果结构扁平化

**文档**:
- 新增 `docs/p1_p2_optimization_implementation.md` - 详细实现文档
- 新增 `scripts/test_optimization_p1_p2.py` - 集成测试脚本

**API端点**:
- `POST /api/optimization/jobs` - 创建优化任务
- `POST /api/optimization/jobs/{job_id}/start` - 启动优化任务
- `GET /api/optimization/jobs/{job_id}` - 获取任务状态
- `GET /api/optimization/jobs/{job_id}/results` - 获取优化结果

---

### Previous Changes

#### 2025-12-16
- 修复 Claude 分析启用问题
- 修复平仓方法调用错误
- 优化市场状态判断逻辑

#### 2025-12-15
- 实现 Policy Layer 架构
- 添加 ML 信号过滤器
- 实现预测技术分析

#### 2024-12
- 交易优化和策略改进
- 添加飞书推送过滤
- 实现方向过滤器
