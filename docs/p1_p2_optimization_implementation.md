# P1/P2 优化实现文档

**日期**: 2026-01-17
**版本**: v1.0
**状态**: 已完成

## 概述

本次实现解决了优化服务中的P1和P2级别问题，使优化功能能够执行真实的回测而非返回模拟数据。

## 问题背景

### P1: 优化服务返回模拟数据
- **问题**: `optimization_service.py` 中的回测函数返回硬编码的模拟指标
- **影响**: 优化结果不反映真实策略性能

### P2: Repository缺少必要方法
- **问题**: `SQLiteRepository` 缺少 `load_kline_dataset()` 和 `get_strategy_version()` 方法
- **影响**: 无法加载K线数据和策略信息进行真实回测

## 实现方案

### 1. Repository层增强

**文件**: `backtest/adapters/storage/sqlite_repo.py`

新增方法:
- `load_kline_dataset(kline_dataset_id)` - 加载并解压K线数据集
- `get_strategy_version(strategy_version_id)` - 获取策略版本信息

```python
async def load_kline_dataset(self, kline_dataset_id: str) -> pd.DataFrame:
    """加载K线数据集"""
    conn = self._get_conn()
    try:
        cursor = conn.execute("SELECT data FROM kline_datasets WHERE id = ?", (kline_dataset_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"K线数据集不存在: {kline_dataset_id}")
        compressed_data = row[0]
        json_data = zlib.decompress(compressed_data).decode()
        klines = json.loads(json_data)
        df = pd.DataFrame(klines)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    finally:
        conn.close()
```

### 2. 优化服务性能优化

**文件**: `backtest/services/optimization_service.py`

**关键改进**:
- 数据预加载: 避免每次迭代重复加载K线数据和策略信息
- 真实回测执行: 调用 `BacktestService.run_backtest()` 执行真实回测
- 异常处理: 捕获异常并更新任务状态为 'failed'

```python
# 预加载数据（避免每次迭代重复加载）
klines = None
strategy_info = None
if self.backtest_service:
    klines = await self.repo.load_kline_dataset(kline_dataset_id)
    strategy_info = await self.repo.get_strategy_version(strategy_version_id)

# 执行回测
if self.backtest_service and klines is not None and strategy_info is not None:
    result = await self.backtest_service.run_backtest(
        run_id, klines, strategy_info['name'], params
    )
    return {**result['metrics'], 'run_id': run_id, 'param_set_id': param_set_id}
```

### 3. API层服务注入

**文件**: `apps/api/routes/optimization.py`

**改进**:
- 注入 `BacktestService` 和 `DataService`
- 使用 `data_service.get_or_fetch_klines()` 获取真实数据集ID
- 添加并发控制: 使用原子性UPDATE防止重复启动

```python
# 初始化服务
backtest_service = BacktestService(repo, cache)
data_service = DataService(repo, cache, provider)
optimization_service = OptimizationService(repo, backtest_service)

# 原子性检查并更新状态
cursor = conn.execute("""
    UPDATE optimization_jobs
    SET status = 'running'
    WHERE id = ? AND status IN ('created', 'failed')
""", (job_id,))
```

### 4. 策略参数兼容性

**文件**: `strategies/strategies.py`

**改进**: 修改 `BaseStrategy.__init__` 接受 `**kwargs` 以支持优化参数

```python
def __init__(self, df: pd.DataFrame, **kwargs):
    self.df = df
    self.ind = IndicatorCalculator(df)
    self.params = kwargs  # 保存优化参数供子类使用
```

### 5. 优化结果结构扁平化

**文件**: `backtest/optimization/grid_search.py`, `backtest/optimization/genetic.py`

**改进**: 将 `run_id` 和 `param_set_id` 提升到结果顶层

```python
result = {
    'params': params,
    'metrics': metrics,
    'score': metrics.get(target_metric, 0),
    'run_id': metrics.get('run_id'),
    'param_set_id': metrics.get('param_set_id')
}
```

## API端点

### POST /api/optimization/jobs
创建优化任务

**请求体**:
```json
{
  "strategy_name": "MACrossStrategy",
  "strategy_version": "1.0",
  "symbol": "BTC/USDT:USDT",
  "timeframe": "1h",
  "start_ts": 1704067200000,
  "end_ts": 1735689600000,
  "algorithm": "grid",
  "search_space": {
    "fast_period": [5, 10, 15],
    "slow_period": [20, 30, 40]
  },
  "target_metric": "sharpe"
}
```

**响应**:
```json
{
  "job_id": "uuid",
  "status": "created"
}
```

### POST /api/optimization/jobs/{job_id}/start
启动优化任务（后台执行）

### GET /api/optimization/jobs/{job_id}
获取任务状态

### GET /api/optimization/jobs/{job_id}/results?limit=50
获取优化结果（Top N）

## 测试验证

运行测试脚本:
```bash
python scripts/test_optimization_p1_p2.py
```

## 性能指标

- **数据预加载**: 减少重复数据库查询，提升优化速度
- **并发控制**: 防止重复任务执行
- **异常处理**: 确保任务状态正确更新

## 相关文件

- `backtest/adapters/storage/sqlite_repo.py` - Repository实现
- `backtest/services/optimization_service.py` - 优化服务
- `backtest/services/backtest_service.py` - 回测服务
- `apps/api/routes/optimization.py` - API端点
- `strategies/strategies.py` - 策略基类
- `backtest/optimization/grid_search.py` - 网格搜索
- `backtest/optimization/genetic.py` - 遗传算法

## 后续优化建议

1. 添加优化任务取消功能
2. 实现优化进度实时推送（WebSocket）
3. 支持分布式优化（多进程/多机器）
4. 添加优化结果可视化
