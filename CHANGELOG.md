# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
