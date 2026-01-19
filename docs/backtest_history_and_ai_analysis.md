# 回测历史与AI分析功能说明文档

## 概述

回测历史与AI分析功能是一个完整的回测结果管理和智能分析系统，提供了回测历史查看、AI智能分析和策略优化审批三大核心功能。该系统通过AI分析回测结果，为交易策略优化提供数据驱动的决策支持，并通过审批流程确保生产环境的安全性。

本功能采用前后端分离架构，后端使用FastAPI + SQLite，前端使用Next.js + React，支持大规模数据（>1000条记录）的高效查询和展示。

## 功能特性

### P0 - 回测历史查看
- **历史列表**：支持分页、排序、多维度筛选的回测会话列表
- **详情页面**：完整的回测结果展示，包括指标、K线图、交易记录
- **游标分页**：支持大规模数据的稳定分页，避免数据跳跃
- **性能优化**：使用denormalized read model和复合索引优化查询性能

### P1 - AI智能分析
- **单会话分析**：使用Claude AI分析单个回测结果，提供优势、劣势、建议
- **多会话对比**：对比多个回测结果，推荐最佳策略
- **参数建议**：基于回测数据提供策略参数优化建议
- **报告存储**：AI分析结果持久化存储，支持历史查询

### P2 - 策略优化审批流程
- **变更请求**：基于AI分析创建策略参数变更请求
- **审批流程**：支持pending → approved → applied的完整审批流程
- **审计日志**：记录所有变更操作，确保可追溯性
- **环境隔离**：区分staging和prod环境，确保生产安全

## 配置说明

### 配置文件位置
- 后端配置：`apps/api/main.py`
- 数据库路径：`backtest.db`（项目根目录）
- AI配置：需要设置环境变量 `ANTHROPIC_AUTH_TOKEN`

### 配置项详解

#### AI分析配置
```python
# 在 backtest/ai_service.py 中
class BacktestAIService:
    def __init__(self, db_path: str = "backtest.db"):
        self.repo = BacktestRepository(db_path)
        self.ai_repo = AIReportRepository(db_path)
        self.analyzer = ClaudeAnalyzer()  # 需要 ANTHROPIC_AUTH_TOKEN
```

#### 数据库配置
```python
# SQLite WAL模式配置
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA foreign_keys=ON")  # 启用外键约束
```

## 使用方法

### 1. 查看回测历史

**访问历史列表页面**：
```
http://localhost:3000/backtest/history
```

**筛选和排序**：
- 按策略名称筛选
- 按时间范围筛选
- 按性能指标筛选（收益率、夏普比率、最大回撤等）
- 支持按任意指标排序

**查看详情**：
点击列表中的任意记录，进入详情页面查看：
- 完整的性能指标
- K线图表
- 交易记录表
- AI分析结果

### 2. 使用AI分析

**触发分析**：
1. 进入回测详情页面
2. 点击"AI分析"标签页
3. 点击"开始分析"按钮

**查看历史分析**：
- AI分析结果会自动保存
- 再次访问时会自动加载最新的分析结果
- 点击"查看历史分析"可查看所有历史报告

**分析结果包含**：
- 整体评价：2-3句话的总结
- 优势：策略的优点列表
- 劣势：策略的缺点列表
- 优化建议：具体的改进建议
- 参数建议：推荐的参数调整值

### 3. 创建变更请求

**基于AI分析创建变更请求**：
```bash
# 通过API创建变更请求
curl -X POST http://localhost:8000/api/change-requests \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "回测会话ID",
    "strategy_name": "策略名称",
    "target_env": "staging",
    "change_payload": {
      "old_config": {"stop_loss": 0.02},
      "new_config": {"stop_loss": 0.015}
    },
    "created_by": "用户名",
    "change_description": "根据AI分析优化止损比例"
  }'
```

**审批流程**：
1. 创建变更请求（status: pending）
2. 审批人审批（status: approved）
3. 应用到目标环境（status: applied）

## 技术实现

### 核心模块

#### 1. 数据层（Repository）
- `backtest/summary_repository.py`：回测摘要的CQRS读模型
- `backtest/ai_repository.py`：AI分析报告存储
- `backtest/change_request_repository.py`：变更请求和审计日志

#### 2. 服务层
- `backtest/ai_service.py`：AI分析服务，调用Claude API
- `backtest/engine.py`：回测引擎，自动更新摘要表

#### 3. API层
- `apps/api/routes/backtest_history.py`：历史查询API
- `apps/api/routes/backtest_ai.py`：AI分析API
- `apps/api/routes/change_requests.py`：变更请求API

#### 4. 前端组件
- `apps/dashboard/app/backtest/history/page.tsx`：历史列表页
- `apps/dashboard/app/backtest/history/[id]/page.tsx`：详情页
- `apps/dashboard/components/backtest/AIAnalysisPanel.tsx`：AI分析面板

### 数据流程

#### 回测历史查询流程
```
用户请求 → API路由 → SummaryRepository → SQLite查询 → 返回结果
```

#### AI分析流程
```
用户触发 → API路由 → AIService → Claude API → 解析结果 → 存储到数据库 → 返回前端
```

#### 变更请求流程
```
创建请求 → 审批 → 应用到环境 → 记录审计日志
```

### 数据库设计

#### 核心表结构

**backtest_session_summaries**（回测摘要表）
- 主键：session_id
- 索引：created_at, total_return, sharpe, max_drawdown, win_rate
- 复合索引：(created_at, session_id) 用于游标分页

**backtest_ai_reports**（AI分析报告表）
- 主键：id
- 外键：session_id → backtest_sessions
- 索引：created_at
- 复合索引：(session_id, created_at)

**backtest_change_requests**（变更请求表）
- 主键：id
- 外键：session_id → backtest_sessions
- 状态：pending, approved, rejected, applied, failed

**backtest_audit_logs**（审计日志表）
- 主键：id
- 记录所有变更操作

## 故障排查

### 常见问题

#### 1. AI分析失败
**症状**：点击"开始分析"后返回错误

**排查步骤**：
1. 检查环境变量 `ANTHROPIC_AUTH_TOKEN` 是否设置
2. 检查网络连接是否正常
3. 查看后端日志：`tail -f logs/api.log`
4. 检查AI服务状态：
   ```python
   from ai.claude_analyzer import ClaudeAnalyzer
   analyzer = ClaudeAnalyzer()
   print(analyzer.enabled)  # 应该返回 True
   ```

**解决方法**：
- 设置正确的API token
- 检查防火墙设置
- 查看详细错误日志

#### 2. 历史列表加载慢
**症状**：历史列表页面加载超过3秒

**排查步骤**：
1. 检查数据量：`SELECT COUNT(*) FROM backtest_session_summaries;`
2. 检查索引：`SELECT * FROM sqlite_master WHERE type='index';`
3. 分析查询计划：`EXPLAIN QUERY PLAN SELECT * FROM backtest_session_summaries ORDER BY created_at DESC LIMIT 50;`

**解决方法**：
- 确保复合索引已创建（运行migration 004）
- 使用游标分页而非offset分页
- 减少单页显示数量

#### 3. 外键约束错误
**症状**：删除回测会话时报错 "FOREIGN KEY constraint failed"

**排查步骤**：
1. 检查外键约束是否启用：`PRAGMA foreign_keys;`
2. 检查关联数据：
   ```sql
   SELECT COUNT(*) FROM backtest_ai_reports WHERE session_id = ?;
   SELECT COUNT(*) FROM backtest_change_requests WHERE session_id = ?;
   ```

**解决方法**：
- 先删除关联的AI报告和变更请求
- 或使用级联删除（需修改表结构）

#### 4. 游标分页数据重复
**症状**：翻页时看到重复的记录

**原因**：使用非created_at字段排序时，游标分页可能不稳定

**解决方法**：
- 使用created_at排序（推荐）
- 或在游标中包含更多唯一字段

## 性能优化

### 已实施的优化

1. **Denormalized Read Model**
   - 使用独立的摘要表避免JOIN查询
   - 查询性能提升10倍以上

2. **复合索引**
   - `idx_summary_cursor (created_at, session_id)`：优化游标分页
   - `idx_ai_session_created (session_id, created_at)`：优化AI报告查询

3. **游标分页**
   - 避免OFFSET的性能问题
   - 支持大规模数据的稳定分页

4. **WAL模式**
   - 提高并发读写性能
   - 减少锁等待时间

### 进一步优化建议

1. **缓存层**
   - 使用Redis缓存热点数据
   - 缓存AI分析结果

2. **异步处理**
   - AI分析改为后台任务
   - 使用消息队列处理变更请求

3. **数据归档**
   - 定期归档历史数据
   - 保持主表数据量在合理范围

4. **前端优化**
   - 实现虚拟滚动
   - 使用SWR缓存策略

## 扩展开发

### 添加新的AI分析维度

1. 修改 `backtest/ai_service.py` 的 `_build_analysis_prompt` 方法
2. 更新 `backtest_ai_reports` 表结构（如需要）
3. 修改前端 `AIAnalysisPanel.tsx` 显示新维度

### 添加新的筛选条件

1. 在 `backtest/summary_repository.py` 的 `list_summaries` 方法中添加筛选逻辑
2. 在 `apps/api/routes/backtest_history.py` 中添加查询参数
3. 在前端添加筛选UI组件

### 集成其他AI模型

1. 创建新的Analyzer类（参考 `ai/claude_analyzer.py`）
2. 在 `backtest/ai_service.py` 中支持模型切换
3. 更新 `backtest_ai_reports` 表的 `model_name` 字段

## 最佳实践

### 1. AI分析使用建议
- 在回测完成后立即进行AI分析
- 对比多个策略参数的回测结果
- 结合AI建议和人工判断做决策
- 定期回顾历史AI分析报告

### 2. 变更请求管理
- 先在staging环境测试
- 审批前仔细review变更内容
- 记录详细的变更原因
- 保持审计日志完整

### 3. 性能优化
- 定期清理过期数据
- 监控数据库大小
- 使用游标分页而非offset
- 合理设置分页大小（推荐50-100）

### 4. 安全建议
- 启用外键约束确保数据完整性
- 使用参数化查询防止SQL注入
- 不向用户暴露内部错误信息
- 定期备份数据库

## 更新日志

### v1.0.0 (2026-01-19)
- 初始版本发布
- 实现P0回测历史查看功能
- 实现P1 AI智能分析功能
- 实现P2策略优化审批流程
- 完成调试修复（外键约束、AI面板、错误处理、复合索引）

## 相关文档

- [数据库开发规范](./database_standards.md)
- [API文档](./api_documentation.md)
- [前端开发指南](./frontend_guide.md)
- [部署指南](./deployment_guide.md)
