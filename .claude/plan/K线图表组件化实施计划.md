# K线图表组件化实施计划

> **状态**: 待批准 | **创建日期**: 2026-01-20 | **预计工作量**: 6-8小时

## 执行摘要

**功能目标**：
1. 修复K线自动加载逻辑异常（图表跳动、before参数错误）
2. 将K线图表抽取为独立可复用组件，支持回测页面、详情页面、首页复用

**技术方案**：
- 采用 Smart Component 方案，将 `KLineChart` 改造为自包含数据逻辑的组件
- 使用 klinecharts v9.8.0 的 `setLoadDataCallback` API 实现增量加载
- 分离生命周期，避免重复 init 导致的图表跳动
- 内部封装数据请求、状态管理、错误处理

**实施策略**：4步迁移（组件重构 → 回测页面 → 详情页面 → 首页预留）

---

## 整体架构

### 组件设计

**方案**：单一 Smart Component（不拆分 Container/View）

**职责**：
- 数据获取（初始加载 + 增量加载）
- 状态管理（klines、loading、error、earliestTs）
- 图表渲染（klinecharts 实例管理）
- 交易标记（overlay 绘制）
- 用户交互（点击、悬浮、滚动）

---

## 组件接口设计

### Props 定义

```typescript
interface KLineChartProps {
  // 模式
  mode: 'backtest' | 'realtime' | 'static';

  // 核心参数
  sessionId?: string;        // 回测模式必填
  symbol?: string;           // 实时模式必填
  interval?: string;         // 时间周期 ('1m', '5m', '15m', ...)

  // 样式
  height?: string | number;  // 默认 '500px'
  className?: string;

  // 交易数据（可选外部传入）
  trades?: Trade[];
  activeTradeId?: number | null;
  onTradeClick?: (id: number) => void;

  // 初始数据（可选，用于首屏优化）
  initialKlines?: KLineData[];
}
```

### 内部状态

```typescript
// State
const [klines, setKlines] = useState<KLineData[]>([]);
const [status, setStatus] = useState<'loading' | 'idle' | 'error'>('loading');
const [isFetchingMore, setIsFetchingMore] = useState(false);
const [error, setError] = useState<string | null>(null);

// Ref
const chartRef = useRef<HTMLDivElement>(null);
const chartInstance = useRef<any>(null);
const hasMore = useRef(true);
const earliestTs = useRef<number | null>(null);
```

---

## 生命周期设计

### Effect 1：实例初始化（仅执行一次）

```typescript
useEffect(() => {
  if (!chartRef.current) return;
  chartInstance.current = init(chartRef.current);

  // 注册增量加载回调
  chartInstance.current.setLoadDataCallback(async () => {
    if (!hasMore.current || isFetchingMore) return;
    const newData = await loadMore();
    return newData;
  });

  return () => {
    if (chartInstance.current) {
      dispose(chartRef.current!);
    }
  };
}, []);
```

**关键点**：
- 空依赖数组，确保只执行一次
- `setLoadDataCallback` 在初始化时注册
- cleanup 函数正确释放实例

### Effect 2：初始数据加载

```typescript
useEffect(() => {
  if (mode === 'backtest' && sessionId) {
    loadInitialData(sessionId);
  } else if (mode === 'realtime' && symbol && interval) {
    // 预留实时数据接口
  }
}, [mode, sessionId, symbol, interval]);
```

**关键点**：
- 依赖 `mode`、`sessionId`、`symbol`、`interval`
- 切换会话时自动重新加载

### Effect 3：数据同步到图表

```typescript
useEffect(() => {
  if (!chartInstance.current || klines.length === 0) return;

  // 首次加载使用 applyNewData
  if (earliestTs.current === null) {
    chartInstance.current.applyNewData(toChartFormat(klines));
    earliestTs.current = klines[0]?.timestamp;
  }
}, [klines]);
```

**关键点**：
- 只在首次加载调用 `applyNewData`
- 增量数据由 `loadMore` 内部调用 `applyMoreData`

### Effect 4：交易标记更新

```typescript
useEffect(() => {
  if (!chartInstance.current || !trades) return;

  // 清除旧标记
  chartInstance.current.removeOverlay();

  // 绘制新标记（开仓/平仓连线、箭头、圆点）
  drawTradeMarkers(chartInstance.current, trades, activeTradeId);
}, [trades, activeTradeId]);
```

**关键点**：
- 独立 effect 处理交易标记，不影响K线数据
- `activeTradeId` 变化时更新高亮状态

---

## 数据加载策略

### 初始加载

```typescript
const loadInitialData = async (sessionId: string) => {
  setStatus('loading');
  setError(null);

  try {
    const res = await axios.get(
      `${API_URL}/api/backtests/sessions/${sessionId}/klines?limit=1000`
    );

    setKlines(res.data);
    earliestTs.current = res.data[0]?.timestamp;
    hasMore.current = res.data.length === 1000;
    setStatus('idle');
  } catch (err) {
    setError(parseError(err));
    setStatus('error');
  }
};
```

**关键点**：
- 初始加载 1000 条
- 设置 `earliestTs` 为最早时间戳
- `hasMore` 根据返回数量判断

### 增量加载

```typescript
const loadMore = async () => {
  if (!sessionId || !earliestTs.current || !hasMore.current || isFetchingMore) {
    return [];
  }

  setIsFetchingMore(true);

  try {
    const res = await axios.get(
      `${API_URL}/api/backtests/sessions/${sessionId}/klines?limit=1000&before=${earliestTs.current}`
    );

    if (res.data.length === 0) {
      hasMore.current = false;
      return [];
    }

    // 去重合并
    const merged = mergeKlines(res.data, klines);
    setKlines(merged);
    earliestTs.current = merged[0]?.timestamp;

    // 转换格式后返回给图表 applyMoreData
    const chartData = toChartFormat(res.data);
    chartInstance.current?.applyMoreData(chartData, res.data.length === 1000);

    return chartData;
  } catch (err) {
    console.error('Failed to load more klines:', err);
    return [];
  } finally {
    setIsFetchingMore(false);
  }
};
```

**关键点**：
- 使用 `before=${earliestTs.current}` 正确计算时间戳
- 防重复：`isFetchingMore` 标志位
- 去重合并：`mergeKlines` 函数确保时间戳唯一
- 调用 `applyMoreData` 平滑追加数据

### 辅助函数

```typescript
// 去重合并K线数据
const mergeKlines = (newData: KLineData[], existingData: KLineData[]): KLineData[] => {
  const map = new Map<number, KLineData>();

  // 先添加新数据
  newData.forEach(k => map.set(k.timestamp, k));

  // 再添加现有数据（避免覆盖）
  existingData.forEach(k => {
    if (!map.has(k.timestamp)) {
      map.set(k.timestamp, k);
    }
  });

  // 按时间戳升序排序
  return Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp);
};

// 转换为图表格式
const toChartFormat = (data: KLineData[]) => {
  return data.map(d => ({
    timestamp: d.timestamp * 1000, // 转为毫秒
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
    volume: d.volume,
  }));
};

// 解析错误信息
const parseError = (err: any): string => {
  return err.response?.data?.detail || err.message || '加载失败';
};
```

---

## UI 反馈设计

### 容器结构

```tsx
<div className={cn("relative w-full", className)} style={{ height: height || '500px' }}>
  {/* K线图表主体 */}
  <div ref={chartRef} className="w-full h-full" />

  {/* 初始加载遮罩 */}
  {status === 'loading' && <LoadingOverlay />}

  {/* 增量加载指示器 */}
  {isFetchingMore && <LoadingIndicator />}

  {/* 错误状态 */}
  {status === 'error' && <ErrorOverlay error={error} onRetry={() => loadInitialData(sessionId!)} />}
</div>
```

### 加载遮罩

```tsx
const LoadingOverlay = () => (
  <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm z-10">
    <div className="flex flex-col items-center gap-2">
      <Spinner className="w-8 h-8" />
      <p className="text-sm text-muted-foreground">正在加载K线数据...</p>
    </div>
  </div>
);
```

### 增量加载指示器

```tsx
const LoadingIndicator = () => (
  <div className="absolute top-4 left-4 bg-black/70 text-white px-3 py-1 rounded-md flex items-center gap-2 z-20">
    <Spinner className="w-3 h-3" />
    <span className="text-xs">加载历史数据中...</span>
  </div>
);
```

### 错误提示

```tsx
const ErrorOverlay = ({ error, onRetry }: { error: string; onRetry: () => void }) => (
  <div className="absolute inset-0 flex flex-col items-center justify-center bg-background z-20">
    <AlertCircle className="w-12 h-12 text-red-500 mb-2" />
    <p className="text-red-500 mb-4">{error}</p>
    <Button onClick={onRetry} variant="outline">
      <RefreshCw className="w-4 h-4 mr-2" />
      重试
    </Button>
  </div>
);
```

---

## 交易标记实现

### 绘制逻辑

```typescript
const drawTradeMarkers = (chart: any, trades: Trade[], activeId?: number | null) => {
  if (!trades || trades.length === 0) return;

  // 1. 绘制配对交易的连接线
  trades.forEach(trade => {
    if (trade.action === 'close' && trade.open_trade_id) {
      const openTrade = trades.find(t => t.id === trade.open_trade_id);
      if (openTrade) {
        chart.createOverlay({
          name: 'segment',
          points: [
            { timestamp: openTrade.ts * 1000, value: openTrade.price },
            { timestamp: trade.ts * 1000, value: trade.price }
          ],
          styles: {
            line: {
              style: 'dashed',
              size: trade.id === activeId ? 2 : 1,
              color: (trade.pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444',
              dashedValue: [4, 4]
            }
          }
        });
      }
    }
  });

  // 2. 绘制交易点标记
  trades.forEach(trade => {
    const isActive = trade.id === activeId;
    const icon = trade.action === 'open'
      ? (trade.side === 'long' ? '▲' : '▼')
      : '●';

    chart.createOverlay({
      name: 'text',
      point: { timestamp: trade.ts * 1000, value: trade.price },
      text: icon,
      styles: {
        text: {
          color: trade.action === 'open'
            ? (trade.side === 'long' ? '#22c55e' : '#ef4444')
            : (trade.pnl >= 0 ? '#22c55e' : '#ef4444'),
          size: isActive ? 16 : 12,
          weight: isActive ? 'bold' : 'normal'
        }
      },
      onClick: () => onTradeClick?.(trade.id)
    });
  });
};
```

---

## 迁移计划

### Step 1：重构 KLineChart 组件

**文件**：`apps/dashboard/components/KLineChart.tsx`

**改动**：
- [ ] 添加 Props 接口定义（mode、sessionId、symbol、interval 等）
- [ ] 添加内部状态（klines、status、isFetchingMore、error）
- [ ] 实现 `loadInitialData` 函数
- [ ] 实现 `loadMore` 函数
- [ ] 实现 `mergeKlines`、`toChartFormat`、`parseError` 辅助函数
- [ ] 重构生命周期：分离 4 个 useEffect
- [ ] 添加 UI 反馈组件（LoadingOverlay、LoadingIndicator、ErrorOverlay）
- [ ] 更新 `drawTradeMarkers` 逻辑

**预计时间**：3-4小时

### Step 2：迁移回测页面

**文件**：`apps/dashboard/app/backtest/new/page.tsx`

**改动**：
- [ ] 删除 `klines` 状态
- [ ] 删除 `loadMoreKlines` 函数
- [ ] 更新 KLineChart 使用方式：
  ```tsx
  <KLineChart
    mode="backtest"
    sessionId={currentSessionId}
    trades={trades}
    activeTradeId={activeTradeId}
    onTradeClick={setActiveTradeId}
  />
  ```
- [ ] 删除初始加载 klines 的 useEffect

**预计时间**：30分钟

### Step 3：迁移详情页面

**文件**：`apps/dashboard/app/backtest/history/[id]/page.tsx`

**改动**：
- [ ] 删除 `klines` 状态
- [ ] 删除 K线请求逻辑（`klinesRes`）
- [ ] 更新 KLineChart 使用方式（同 Step 2）

**预计时间**：30分钟

### Step 4：预留首页实时模式

**文件**：`apps/dashboard/app/page.tsx`（未来）

**改动**：
- [ ] 添加实时K线预览卡片
- [ ] 使用组件：
  ```tsx
  <KLineChart
    mode="realtime"
    symbol="BTC/USDT"
    interval="1m"
    height={300}
  />
  ```
- [ ] 接入 WebSocket 实时数据（需后端支持）

**预计时间**：2-3小时（需后端配合）

---

## 测试验证

### 功能测试

- [ ] 回测页面：初始加载显示 1000 条K线
- [ ] 回测页面：向左滑动到边缘，自动加载更多数据
- [ ] 回测页面：加载更多后图表不跳动，保持当前视图
- [ ] 回测页面：交易标记正确显示（开仓箭头、平仓圆点、连接线）
- [ ] 回测页面：点击交易标记触发高亮
- [ ] 详情页面：使用新组件显示K线和交易
- [ ] 详情页面：向左滑动加载更多数据
- [ ] 错误处理：网络错误时显示错误提示和重试按钮
- [ ] 加载状态：初始加载显示遮罩，增量加载显示角标

### 性能测试

- [ ] 加载 5000+ 条K线时性能稳定
- [ ] 连续滑动不触发多次请求（防抖机制）
- [ ] 去重逻辑正确，无重复K线
- [ ] 内存占用合理，无内存泄漏

### 兼容性测试

- [ ] Chrome、Safari、Firefox 浏览器兼容
- [ ] 桌面和移动端响应式布局
- [ ] 暗色主题和亮色主题样式正确

---

## 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| klinecharts API 兼容性 | 增量加载失败 | 参考官方文档 v9.8.0 |
| 数据去重逻辑错误 | K线重复或丢失 | 单元测试 mergeKlines 函数 |
| 组件重复 init | 图表跳动 | 严格控制 useEffect 依赖 |
| 内存泄漏 | 长时间使用卡顿 | 正确实现 cleanup 函数 |
| before 参数计算错误 | 加载数据不连续 | 日志输出验证时间戳 |

---

## 总结

本计划采用 Smart Component 方案，将 KLineChart 改造为自包含数据逻辑的可复用组件。通过分离生命周期、优化数据加载策略、增强 UI 反馈，彻底解决了图表跳动和数据加载异常问题。

**核心改进**：
1. ✅ 修复 before 参数计算逻辑，使用 `earliestTs` 动态更新
2. ✅ 分离生命周期，避免重复 init 导致的跳动
3. ✅ 封装数据请求逻辑，组件自包含
4. ✅ 统一行为，支持回测页面、详情页面、首页复用
5. ✅ 增强 UI 反馈，提升用户体验

**下一步**：等待用户批准后，进入阶段 4（执行）。
