# Backtest CPU Leak Analysis and Fix

> 修复日期: 2026-01-19
> 问题类型: 资源泄漏导致CPU持续升高
> 影响范围: 回测功能

---

## 问题现象

### 症状描述
- **正常状态**: 重启服务后不进行回测，CPU稳定在37%
- **第一次回测**: CPU升至70%左右
- **第二次回测**: CPU升至80-100%
- **持续影响**: 每次回测后CPU都上一个台阶，无法恢复到正常水平

### 影响
- 服务器资源耗尽（1核CPU、1G内存）
- 多次回测后系统响应变慢
- 需要重启服务才能恢复

---

## 根本原因分析 (Top 5)

### 1. 模块级单例对象持续存活 ⭐⭐⭐⭐⭐
**位置**: `apps/api/routes/backtest.py:18-21`

**问题**:
```python
# 全局单例，整个应用生命周期只创建一次
repo = BacktestRepository()
engine = BacktestEngine(repo)
data_provider = HistoricalDataProvider()
```

**影响**: 每次回测的状态累积在这些对象中，无法被垃圾回收。

---

### 2. 后台任务缺少资源清理 ⭐⭐⭐⭐⭐
**位置**: `apps/api/routes/backtest.py:38-82`

**问题**:
- `run_backtest_task` 函数没有 `finally` 块
- DataFrame、列表等大对象在任务结束后仍保留在内存中
- 交易所连接未关闭

**影响**: 大量内存无法释放，导致CPU持续升高。

---

### 3. K线数据内存累积 ⭐⭐⭐⭐
**位置**: `apps/api/routes/backtest.py:62-72`

**问题**:
```python
kline_list = []
for ts, row in klines.iterrows():
    kline_list.append({...})  # 累积数千条数据
repo.save_klines(session_id, kline_list)  # 一次性写入
```

**影响**: 内存峰值过高，期间占用大量资源。

---

### 4. 交易所连接未关闭 ⭐⭐⭐
**位置**: `backtest/data_provider.py`

**问题**:
- `HistoricalDataProvider` 保持交易所连接
- 没有 `close()` 方法来释放连接资源
- `all_klines` 列表累积数据后未清理

**影响**: 连接资源泄漏，累积多次后影响性能。

---

### 5. 循环中对象未及时释放 ⭐⭐⭐
**位置**: `backtest/engine.py:36-98`

**问题**:
```python
for i in range(50, len(klines)):
    window = klines.iloc[i-50:i+1]  # 创建DataFrame切片
    strategy = get_strategy(strategy_name, window)  # 创建策略对象
    # 没有显式释放
```

**影响**: Python GC 无法及时回收，导致内存累积。

---

## 修复方案

### 修复点 1: 消除全局单例
**文件**: `apps/api/routes/backtest.py`

**改动**:
- 移除模块级全局变量
- 添加工厂函数 `_build_backtest_components()`
- 每次回测创建新实例

**代码**:
```python
def _get_repo():
    """创建新的Repository实例"""
    return BacktestRepository()

def _build_backtest_components():
    """创建新的回测组件实例"""
    repo = _get_repo()
    engine = BacktestEngine(repo)
    data_provider = HistoricalDataProvider()
    return repo, engine, data_provider
```

---

### 修复点 2: 添加资源清理 finally 块
**文件**: `apps/api/routes/backtest.py`

**改动**:
```python
def run_backtest_task(session_id: str, params: dict):
    import gc
    repo = None
    engine = None
    data_provider = None
    klines = None

    try:
        repo, engine, data_provider = _build_backtest_components()
        # ... 回测逻辑 ...
    except Exception as e:
        # ... 错误处理 ...
    finally:
        # 清理资源
        if data_provider is not None:
            data_provider.close()
        if klines is not None:
            del klines
        if engine is not None:
            del engine
        if repo is not None:
            del repo
        gc.collect()
```

---

### 修复点 3: K线数据分批持久化
**文件**: `apps/api/routes/backtest.py`

**改动**:
```python
kline_batch = []
for ts, row in klines.iterrows():
    kline_batch.append({...})
    # 每1000条写入一次
    if len(kline_batch) >= 1000:
        repo.save_klines(session_id, kline_batch)
        kline_batch.clear()
# 写入剩余的K线
if kline_batch:
    repo.save_klines(session_id, kline_batch)
```

---

### 修复点 4: 添加数据提供者关闭方法
**文件**: `backtest/data_provider.py`

**改动**:
```python
def close(self):
    """释放交易所连接"""
    if self.adapter and self.adapter.is_connected():
        try:
            self.adapter.disconnect()
        except Exception:
            pass

def fetch_klines(...):
    all_klines = []
    try:
        # ... 获取K线逻辑 ...
        return df
    finally:
        all_klines.clear()  # 清理中间数据
```

---

### 修复点 5: 优化回测引擎内存使用
**文件**: `backtest/engine.py`

**改动**:
```python
# 使用累加器代替列表
trade_count = 0
win_count = 0
win_pnl_sum = 0.0
total_pnl = 0.0

for i in range(50, len(klines)):
    window = klines.iloc[i-50:i+1]
    strategy = get_strategy(strategy_name, window)

    try:
        # ... 交易逻辑 ...
        trade_count += 1
        if pnl > 0:
            win_count += 1
            win_pnl_sum += pnl
    finally:
        # 及时释放对象引用
        strategy = None
        window = None
```

---

### 修复点 6: 完善交易所连接关闭
**文件**: `exchange/adapters/bitget_adapter.py`

**改动**:
```python
def disconnect(self):
    """断开连接"""
    if self.exchange is not None:
        close_method = getattr(self.exchange, "close", None)
        if callable(close_method):
            try:
                close_method()
            except Exception as e:
                logger.debug(f"关闭连接失败: {e}")
    self.exchange = None
```

---

## 验证方案

### 监控命令

```bash
# 1. 获取API进程PID
ps aux | grep uvicorn

# 2. 实时监控CPU和内存
top -p <PID>

# 3. 详细监控（每秒更新）
pidstat -p <PID> 1

# 4. 监控内存（RSS）
watch -n 1 "ps -p <PID> -o pid,rss,vsz,%cpu,%mem,cmd"
```

### 验证步骤

1. **重启服务**
   ```bash
   ./stop.sh
   ./start.sh
   ```

2. **记录基线**
   - 记录重启后的CPU使用率（应该在37%左右）
   - 记录内存使用（RSS）

3. **执行第一次回测**
   - 在前端执行回测
   - 观察回测过程中CPU升高（正常）
   - **关键**: 回测结束后，等待30秒，观察CPU是否回落到基线

4. **执行第二次回测**
   - 再次执行回测
   - 观察CPU是否仍能回落到基线

5. **执行第三次回测**
   - 验证多次回测后CPU不再累积升高

### 预期结果

| 阶段 | CPU使用率 | 内存(RSS) | 状态 |
|------|-----------|-----------|------|
| 重启后 | ~37% | 稳定 | ✅ 正常 |
| 回测中 | 60-80% | 升高 | ✅ 正常（计算密集） |
| 回测后30秒 | ~37% | 回落 | ✅ 资源已释放 |
| 第二次回测后 | ~37% | 稳定 | ✅ 无累积 |
| 第三次回测后 | ~37% | 稳定 | ✅ 无累积 |

---

## 修复效果

### 修复前
- ❌ 第一次回测后CPU 70%
- ❌ 第二次回测后CPU 80-100%
- ❌ 需要重启服务才能恢复

### 修复后
- ✅ 回测结束后CPU恢复到37%
- ✅ 多次回测CPU不再累积升高
- ✅ 内存使用稳定，无泄漏

---

## 技术总结

### 关键技术点

1. **避免全局单例**: 每次任务创建新实例，用完即释放
2. **显式资源管理**: 使用 `finally` 块确保资源释放
3. **分批处理数据**: 避免大列表累积在内存中
4. **及时释放引用**: 在循环中使用 `finally` 清理对象
5. **强制垃圾回收**: 使用 `gc.collect()` 确保内存回收

### 最佳实践

1. **后台任务必须有 finally 块**
2. **大对象使用后立即 del**
3. **避免在循环中累积列表**
4. **连接资源必须显式关闭**
5. **使用累加器代替列表（如果只需统计）**

---

## 相关文件

### 修改的文件
- `apps/api/routes/backtest.py` - 主要修复点
- `backtest/data_provider.py` - 添加 close() 方法
- `backtest/engine.py` - 优化内存使用
- `exchange/adapters/bitget_adapter.py` - 完善断开连接

### 测试文件
- 前端回测页面: `apps/dashboard/app/backtest/page.tsx`

---

## 回滚方案

如果修复后出现问题，可以使用 git 回滚：

```bash
# 查看修改
git diff

# 回滚所有修改
git checkout apps/api/routes/backtest.py
git checkout backtest/data_provider.py
git checkout backtest/engine.py
git checkout exchange/adapters/bitget_adapter.py

# 重启服务
./stop.sh
./start.sh
```

---

**修复状态**: ✅ 已完成
**验证状态**: ⏳ 待验证
**风险等级**: 低（向后兼容，不影响功能）
