# 交易数据可视化项目 - 前端Dashboard设计

**文档版本**: v1.0
**创建时间**: 2026-01-09

---

## 1. 页面结构设计

### 1.1 整体布局

```
┌─────────────────────────────────────────────────────────┐
│  Header                                                  │
│  [Logo] Trading Dashboard        [User] [Settings]      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│  │ 余额   │ │ 持仓   │ │ 盈亏   │ │ 胜率   │  ← 指标卡片
│  │ 1000U  │ │ 0.001  │ │ +1.5U  │ │ 65%    │          │
│  └────────┘ └────────┘ └────────┘ └────────┘          │
│                                                          │
│  ┌──────────────────────┐ ┌──────────────────────┐    │
│  │  当前趋势图表         │ │  生效指标面板         │    │
│  │  ┌────────────────┐  │ │  ┌────────────────┐  │    │
│  │  │  LineChart     │  │ │  │  RSI: 65.5     │  │    │
│  │  │  (Recharts)    │  │ │  │  MACD: 150.0   │  │    │
│  │  └────────────────┘  │ │  │  EMA: 50500    │  │    │
│  └──────────────────────┘ │  └────────────────┘  │    │
│                            └──────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  历史交易记录 (DataTable)                        │   │
│  │  [筛选] [搜索] [导出]                            │   │
│  │  ┌───────────────────────────────────────────┐  │   │
│  │  │ ID | 时间 | 策略 | 价格 | 盈亏 | 操作    │  │   │
│  │  ├───────────────────────────────────────────┤  │   │
│  │  │ 1  | 10:30| Mom | 50000| +1.0 | [详情]  │  │   │
│  │  └───────────────────────────────────────────┘  │   │
│  │  [上一页] [1] [2] [3] [下一页]                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
│  [AI 聊天] 💬                                           │ ← 固定底部
└─────────────────────────────────────────────────────────┘
```

---

## 2. 组件设计

### 2.1 指标卡片组件

**组件**: `MetricCard`

**Props**:
```typescript
interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;  // 变化百分比
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}
```

**shadcn/ui 组件**:
- `Card`
- `CardHeader`
- `CardContent`
- `Badge`

**示例**:
```tsx
<MetricCard
  title="账户余额"
  value="1000.00 USDT"
  change={+2.5}
  trend="up"
  icon={<DollarSign />}
/>
```

---

### 2.2 趋势图表组件

**组件**: `TrendChart`

**Props**:
```typescript
interface TrendChartProps {
  data: Array<{
    timestamp: string;
    price: number;
    volume?: number;
  }>;
  indicators?: {
    ema20?: number[];
    ema50?: number[];
  };
}
```

**图表库**: Recharts

**图表类型**:
- `LineChart` - 价格走势
- `AreaChart` - 成交量
- `ComposedChart` - 组合图表

**示例**:
```tsx
<TrendChart
  data={priceData}
  indicators={{
    ema20: ema20Data,
    ema50: ema50Data
  }}
/>
```

---

### 2.3 指标面板组件

**组件**: `IndicatorPanel`

**Props**:
```typescript
interface IndicatorPanelProps {
  indicators: Array<{
    name: string;
    value: number;
    signal: 'bullish' | 'bearish' | 'neutral';
    threshold?: {
      overbought?: number;
      oversold?: number;
    };
  }>;
}
```

**shadcn/ui 组件**:
- `Card`
- `Badge`
- `Progress`
- `Tooltip`

**示例**:
```tsx
<IndicatorPanel
  indicators={[
    { name: 'RSI', value: 65.5, signal: 'neutral' },
    { name: 'MACD', value: 150, signal: 'bullish' }
  ]}
/>
```

---

### 2.4 历史记录表格组件

**组件**: `TradeHistoryTable`

**Props**:
```typescript
interface TradeHistoryTableProps {
  data: Trade[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
  };
  onPageChange: (page: number) => void;
  onFilter: (filters: TradeFilters) => void;
}
```

**shadcn/ui 组件**:
- `Table`
- `TableHeader`
- `TableBody`
- `TableRow`
- `TableCell`
- `Button`
- `Input`
- `Select`

**功能**:
- 排序（按时间、盈亏）
- 筛选（策略、日期范围）
- 搜索（订单ID）
- 分页
- 导出（CSV）

---

### 2.5 AI 聊天组件

**组件**: `AIChatPanel`

**Props**:
```typescript
interface AIChatPanelProps {
  onSendMessage: (message: string) => Promise<string>;
  initialMessages?: ChatMessage[];
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}
```

**shadcn/ui 组件**:
- `Sheet` (侧边抽屉)
- `ScrollArea`
- `Input`
- `Button`
- `Avatar`

**功能**:
- 消息历史
- 流式响应
- 快捷命令（/analyze, /suggest）
- 上下文感知

---

## 3. 数据管理

### 3.1 API 客户端

**文件**: `lib/api-client.ts`

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  timeout: 10000,
});

// 请求拦截器 - 添加 JWT Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token 过期，跳转登录
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

### 3.2 数据获取 Hooks

**文件**: `hooks/use-trades.ts`

```typescript
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

export function useTrades(params?: {
  limit?: number;
  offset?: number;
  strategy?: string;
}) {
  return useQuery({
    queryKey: ['trades', params],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/trades', { params });
      return data;
    },
    refetchInterval: 30000, // 30秒自动刷新
  });
}
```

**文件**: `hooks/use-position.ts`

```typescript
export function useCurrentPosition() {
  return useQuery({
    queryKey: ['position', 'current'],
    queryFn: async () => {
      const { data } = await apiClient.get('/api/positions/current');
      return data;
    },
    refetchInterval: 5000, // 5秒刷新
  });
}
```

---

### 3.3 WebSocket Hook

**文件**: `hooks/use-websocket.ts`

```typescript
import { useEffect, useState } from 'react';

export function useWebSocket(url: string) {
  const [data, setData] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const ws = new WebSocket(`${url}?token=${token}`);

    ws.onopen = () => {
      setIsConnected(true);
      // 订阅频道
      ws.send(JSON.stringify({
        action: 'subscribe',
        channels: ['trades', 'positions', 'trends']
      }));
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setData(message);
    };

    ws.onclose = () => {
      setIsConnected(false);
      // 自动重连
      setTimeout(() => {
        // 重新连接逻辑
      }, 3000);
    };

    return () => ws.close();
  }, [url]);

  return { data, isConnected };
}
```

---

## 4. 状态管理

### 4.1 全局状态 (Zustand)

**文件**: `store/use-app-store.ts`

```typescript
import { create } from 'zustand';

interface AppState {
  user: User | null;
  theme: 'light' | 'dark';
  setUser: (user: User | null) => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useAppStore = create<AppState>((set) => ({
  user: null,
  theme: 'light',
  setUser: (user) => set({ user }),
  setTheme: (theme) => set({ theme }),
}));
```

---

## 5. 路由设计

### 5.1 页面路由

```
app/
├── layout.tsx           # 根布局
├── page.tsx             # 首页（Dashboard）
├── login/
│   └── page.tsx         # 登录页
└── (dashboard)/         # Dashboard 路由组
    ├── layout.tsx       # Dashboard 布局
    ├── page.tsx         # 概览页
    ├── history/
    │   └── page.tsx     # 历史记录页
    └── settings/
        └── page.tsx     # 设置页
```

---

## 6. 样式设计

### 6.1 主题配置

**文件**: `tailwind.config.js`

```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0fdf4',
          500: '#22c55e',
          900: '#14532d',
        },
        danger: {
          500: '#ef4444',
        },
      },
    },
  },
};
```

### 6.2 全局样式

**文件**: `app/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 142.1 76.2% 36.3%;
  }
}
```

---

## 7. 性能优化

### 7.1 代码分割

```typescript
// 懒加载图表组件
const TrendChart = dynamic(() => import('@/components/charts/TrendChart'), {
  loading: () => <Skeleton className="h-[300px]" />,
  ssr: false,
});
```

### 7.2 虚拟滚动

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

// 长列表使用虚拟滚动
const rowVirtualizer = useVirtualizer({
  count: trades.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 50,
});
```

---

**下一步**: 阅读 `05-实施计划.md` 了解分阶段实施步骤。
