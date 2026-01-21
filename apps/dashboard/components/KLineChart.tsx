'use client';

import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { init, dispose } from 'klinecharts';
import apiClient from '@/lib/api-client';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { TrendingUp, Square, Type } from 'lucide-react';

// ==================== Constants ====================

// 颜色常量 - 使用 Tailwind CSS 变量
const CHART_COLORS = {
  up: 'hsl(var(--trading-up))',
  down: 'hsl(var(--trading-down))',
  primary: 'hsl(var(--primary))',
} as const;

// ==================== Types ====================

type DrawingTool = 'line' | 'rect' | 'text' | null;

interface KLineData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Trade {
  id: number;
  ts: number;
  action: string;
  price: number;
  side: string;
  strategy_name?: string;
  reason?: string;
  qty?: number;
  pnl?: number;
  open_trade_id?: number;
}

interface KLineChartProps {
  // 模式
  mode: 'backtest' | 'realtime' | 'static';

  // 核心参数
  sessionId?: string;        // 回测模式必填
  symbol?: string;           // 实时模式必填
  interval?: string;         // 时间周期

  // 样式
  height?: string | number;
  className?: string;

  // 交易数据（可选外部传入）
  trades?: Trade[];
  activeTradeId?: number | null;
  onTradeClick?: (id: number) => void;
  strategyName?: string;

  // 初始数据（用于 static 模式）
  initialKlines?: KLineData[];
}

// ==================== Component ====================

export default function KLineChart({
  mode,
  sessionId,
  symbol,
  interval,
  height = '500px',
  className,
  trades = [],
  activeTradeId,
  onTradeClick,
  strategyName,
  initialKlines = [],
}: KLineChartProps) {
  // ==================== State ====================
  const [klines, setKlines] = useState<KLineData[]>(initialKlines);
  const [status, setStatus] = useState<'loading' | 'idle' | 'error'>('loading');
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 绘图工具状态
  const [activeTool, setActiveTool] = useState<DrawingTool>(null);
  const [overlays, setOverlays] = useState<string[]>([]);

  // ==================== Refs ====================
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);
  const hasMore = useRef(true);
  const earliestTs = useRef<number | null>(null);
  const isInitialized = useRef(false);
  const loadMoreRef = useRef<(() => Promise<any[]>) | null>(null);
  const isFetchingMoreRef = useRef(false);

  // ==================== Helper Functions ====================

  const parseError = (err: any): string => {
    return err.response?.data?.detail || err.message || '加载失败';
  };

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

  // ==================== Data Loading ====================

  const loadInitialData = async (sid: string) => {
    setStatus('loading');
    setError(null);

    try {
      const res = await apiClient.get(`/api/backtests/sessions/${sid}/klines?limit=1000`);
      const data = res.data || [];

      // 确保升序排序
      const sortedData = data.sort((a: KLineData, b: KLineData) => a.timestamp - b.timestamp);

      setKlines(sortedData);
      earliestTs.current = sortedData.length > 0 ? sortedData[0].timestamp : null;
      hasMore.current = sortedData.length === 1000;

      console.log('[KLineChart] 📊 初始数据加载完成', {
        count: sortedData.length,
        earliestTs: earliestTs.current,
        latestTs: sortedData[sortedData.length - 1]?.timestamp,
        hasMore: hasMore.current
      });

      setStatus('idle');
    } catch (err) {
      setError(parseError(err));
      setStatus('error');
    }
  };

  // 使用 useCallback 避免闭包过期问题
  const loadMore = useCallback(async (): Promise<any[]> => {
    console.log('[KLineChart] loadMore 被调用', {
      sessionId,
      earliestTs: earliestTs.current,
      hasMore: hasMore.current,
      isFetching: isFetchingMoreRef.current
    });

    if (!sessionId || !earliestTs.current || !hasMore.current || isFetchingMoreRef.current) {
      console.log('[KLineChart] ❌ loadMore 提前退出', {
        hasSessionId: !!sessionId,
        hasEarliestTs: !!earliestTs.current,
        hasMore: hasMore.current,
        isFetching: isFetchingMoreRef.current
      });
      return [];
    }

    const currentEarliest = earliestTs.current;
    setIsFetchingMore(true);
    isFetchingMoreRef.current = true;

    try {
      console.log('[KLineChart] 请求数据 before=', currentEarliest);
      const res = await apiClient.get(
        `/api/backtests/sessions/${sessionId}/klines?limit=1000&before=${currentEarliest}`
      );
      const newData = res.data || [];
      console.log('[KLineChart] 收到数据', newData.length, '条');

      // 数据加载完毕的条件
      if (newData.length === 0) {
        console.log('[KLineChart] 无数据，停止加载');
        hasMore.current = false;
        setIsFetchingMore(false);
        isFetchingMoreRef.current = false;
        return [];
      }

      // 确保新数据升序排序
      const sortedNewData = newData.sort((a: KLineData, b: KLineData) => a.timestamp - b.timestamp);
      const newEarliest = sortedNewData[0]?.timestamp;
      console.log('[KLineChart] 新数据最早时间戳', newEarliest, '当前最早', currentEarliest);

      // 检查是否获取到了更早的数据
      if (!newEarliest || newEarliest >= currentEarliest) {
        // 没有更早的数据了，停止加载
        console.log('[KLineChart] 新数据不更早，停止加载');
        hasMore.current = false;
        setIsFetchingMore(false);
        isFetchingMoreRef.current = false;
        return [];
      }

      // 如果返回数据少于 1000 条，可能是最后一批数据
      if (newData.length < 1000) {
        console.log('[KLineChart] 数据少于1000条，标记为最后一批');
        hasMore.current = false;
      }

      // 更新最早时间戳
      earliestTs.current = newEarliest;
      console.log('[KLineChart] 更新 earliestTs 为', newEarliest);

      // 去重合并
      setKlines(prevKlines => {
        return mergeKlines(sortedNewData, prevKlines);
      });

      setIsFetchingMore(false);
      isFetchingMoreRef.current = false;

      // 转换格式后返回给图表 applyMoreData
      return toChartFormat(sortedNewData);
    } catch (err) {
      console.error('[KLineChart] 加载失败:', err);
      hasMore.current = false;
      setIsFetchingMore(false);
      isFetchingMoreRef.current = false;
      return [];
    }
  }, [sessionId]); // 移除 isFetchingMore 依赖

  // 更新 loadMore ref
  useEffect(() => {
    loadMoreRef.current = loadMore;
  }, [loadMore]);

  // ==================== Trade Markers ====================

  // 性能优化：创建 Map 索引，O(n²) → O(n)
  const tradesById = useMemo(
    () => new Map(trades.map(t => [t.id, t])),
    [trades]
  );

  const closeByOpenId = useMemo(() => {
    const map = new Map<number, Trade>();
    for (const t of trades) {
      if (t.action === 'close' && t.open_trade_id) {
        map.set(t.open_trade_id, t);
      }
    }
    return map;
  }, [trades]);

  const drawTradeMarkers = useCallback((
    chart: any,
    tradesList: Trade[],
    tradesMap: Map<number, Trade>,
    closeMap: Map<number, Trade>,
    activeId?: number | null
  ) => {
    if (!chart || !tradesList || tradesList.length === 0) return;

    // 清除旧的交易标记（保留用户绘图）
    chart.getOverlays?.()
      ?.filter((o: any) => o.extendData?.kind === 'trade-marker')
      ?.forEach((o: any) => chart.removeOverlay(o.id));

    // 1. 绘制配对交易的连接线
    tradesList.forEach(trade => {
      if (trade.action === 'close' && trade.open_trade_id) {
        const openTrade = tradesMap.get(trade.open_trade_id);
        if (openTrade) {
          const isPaired = activeId === trade.id || activeId === openTrade.id;

          chart.createOverlay({
            name: 'segment',
            points: [
              { timestamp: openTrade.ts * 1000, value: openTrade.price },
              { timestamp: trade.ts * 1000, value: trade.price }
            ],
            styles: {
              line: {
                style: 'dashed',
                size: isPaired ? 2 : 1,
                color: (trade.pnl ?? 0) >= 0 ? CHART_COLORS.up : CHART_COLORS.down,
                dashedValue: [4, 4]
              }
            },
            extendData: { kind: 'trade-marker' }
          });
        }
      }
    });

    // 2. 绘制交易点标记
    tradesList.forEach(trade => {
      const pairedTrade = trade.action === 'close'
        ? tradesMap.get(trade.open_trade_id!)
        : closeMap.get(trade.id);

      const isPaired = activeId === trade.id || activeId === pairedTrade?.id;

      // 构建交易信息文本
      const tradeInfo = [
        `${trade.action === 'open' ? '开仓' : '平仓'} ${trade.side === 'long' ? '做多' : '做空'}`,
        `价格: ${trade.price.toFixed(2)}`,
        trade.qty ? `数量: ${trade.qty.toFixed(4)}` : '',
        trade.strategy_name ? `策略: ${trade.strategy_name}` : '',
        trade.reason ? `原因: ${trade.reason}` : '',
        trade.pnl ? `盈亏: ${trade.pnl.toFixed(2)}` : '',
        pairedTrade ? `配对: #${pairedTrade.id}` : (trade.action === 'open' ? '未平仓' : '')
      ].filter(Boolean).join('\n');

      // 根据开仓方向和操作类型选择标记样式
      let symbolType = 'circle';
      let symbolColor = '#6b7280';

      if (trade.action === 'open') {
        symbolType = trade.side === 'long' ? 'triangle' : 'invertedTriangle';
        symbolColor = trade.side === 'long' ? CHART_COLORS.up : CHART_COLORS.down;
      } else {
        symbolType = 'circle';
        symbolColor = (trade.pnl ?? 0) >= 0 ? CHART_COLORS.up : CHART_COLORS.down;
      }

      chart.createOverlay({
        name: 'simpleAnnotation',
        points: [{ timestamp: trade.ts * 1000, value: trade.price }],
        styles: {
          symbol: {
            type: symbolType,
            size: isPaired ? 10 : 8,
            color: symbolColor,
            activeColor: CHART_COLORS.primary,
            offset: [0, 0]
          },
          text: {
            style: 'fill',
            size: 0,
            family: 'Helvetica Neue',
            weight: 'normal',
            color: 'transparent',
            backgroundColor: 'transparent',
            borderColor: 'transparent'
          }
        },
        extendData: {
          id: trade.id,
          info: tradeInfo,
          kind: 'trade-marker'
        },
        onClick: () => {
          if (onTradeClick) {
            onTradeClick(trade.id);
          }
        },
      });
    });

    // 3. 根据策略动态创建指标
    if (strategyName) {
      const indicatorMap: Record<string, string> = {
        'bollinger_trend': 'BOLL',
        'bollinger_breakthrough': 'BOLL',
        'macd_cross': 'MACD',
        'ema_cross': 'EMA',
        'rsi_divergence': 'RSI',
        'composite_score': 'MA',
        'multi_timeframe': 'MA',
      };
      const indicator = indicatorMap[strategyName] || 'MA';
      chart.createIndicator(indicator, false, { id: 'candle_pane' });
    }
  }, [strategyName]);

  // ==================== Drawing Tools ====================

  // 保存绘图到 localStorage
  const saveOverlaysToStorage = useCallback((chart: any) => {
    if (!chart || !symbol) return;

    try {
      const allOverlays = chart.getOverlays?.() || [];

      // 仅保存用户绘图
      const overlayData = allOverlays
        .filter((o: any) => o.extendData?.persist === true)
        .map((o: any) => ({
          id: o.id,
          name: o.name,
          points: o.points,
          styles: o.styles,
          extendData: o.extendData,
        }));

      const serialized = JSON.stringify(overlayData);

      // 大小限制：200KB
      if (serialized.length > 200_000) {
        console.warn('绘图数据过大，跳过保存');
        return;
      }

      localStorage.setItem(`kline-overlays-${symbol}`, serialized);
    } catch (error) {
      console.error('保存绘图数据失败:', error);
    }
  }, [symbol]);

  // 工具选择处理
  const handleToolSelect = useCallback((tool: DrawingTool) => {
    if (!chartInstance.current) return;

    // 切换工具状态
    if (activeTool === tool) {
      setActiveTool(null);
      return;
    }

    setActiveTool(tool);

    // 映射到 klinecharts overlay 类型
    const overlayTypeMap: Record<Exclude<DrawingTool, null>, string> = {
      line: 'straightLine',
      rect: 'rect',
      text: 'simpleAnnotation',
    };

    if (tool) {
      // 创建 overlay
      const overlayId = chartInstance.current.createOverlay({
        name: overlayTypeMap[tool],
        styles: {
          line: {
            color: CHART_COLORS.primary,
            size: 2,
          },
          text: {
            color: CHART_COLORS.primary,
            size: 12,
          },
          rect: {
            color: CHART_COLORS.primary,
            borderSize: 2,
            borderColor: CHART_COLORS.primary,
          },
        },
        extendData: {
          persist: true,
          type: 'user-drawing'
        },
        onDrawEnd: ({ overlay, chart }: any) => {
          // 绘制完成后保存
          if (overlay?.id) {
            setOverlays(prev => [...prev, overlay.id]);
            saveOverlaysToStorage(chart);
          }
          // 重置工具状态
          setActiveTool(null);
        },
      });
    }
  }, [activeTool, saveOverlaysToStorage]);

  // 清除所有绘图
  const handleClearAll = useCallback(() => {
    if (!chartInstance.current) return;

    overlays.forEach(id => {
      chartInstance.current?.removeOverlay?.(id);
    });

    setOverlays([]);
    setActiveTool(null);

    // 清除存储
    if (symbol) {
      localStorage.removeItem(`kline-overlays-${symbol}`);
    }
  }, [overlays, symbol]);

  // ==================== Effects ====================

  // Effect 1: 实例初始化（仅执行一次）
  useEffect(() => {
    if (!chartRef.current || isInitialized.current) return;

    chartInstance.current = init(chartRef.current);
    isInitialized.current = true;

    return () => {
      if (chartInstance.current && chartRef.current) {
        dispose(chartRef.current);
        chartInstance.current = null;
        isInitialized.current = false;
      }
    };
  }, []); // 空依赖，只执行一次

  // Effect 1.5: 注册增量加载回调
  useEffect(() => {
    if (!chartInstance.current || mode !== 'backtest' || !sessionId) return;

    // 延迟注册，确保图表完全初始化
    const timer = setTimeout(() => {
      if (!chartInstance.current) return;

      // 创建稳定的回调引用
      const loadDataCallback = async (params: any) => {
        console.log('[KLineChart] 📞 loadDataCallback 被触发', {
          hasMore: hasMore.current,
          isFetching: isFetchingMoreRef.current,
          earliestTs: earliestTs.current,
          params
        });

        // 检查是否还有更多数据（使用 ref 避免闭包问题）
        if (!hasMore.current || isFetchingMoreRef.current) {
          console.log('[KLineChart] ⏸️ 跳过加载：', {
            reason: !hasMore.current ? '无更多数据' : '正在加载中'
          });
          return null; // 返回 null 告诉 klinecharts 停止加载
        }

        // 使用 ref 中的最新 loadMore 函数
        if (!loadMoreRef.current) {
          console.log('[KLineChart] ⚠️ loadMoreRef.current 不存在');
          return null;
        }

        console.log('[KLineChart] ▶️ 开始执行 loadMore');
        const moreData = await loadMoreRef.current();

        // 如果没有数据或数据已加载完，返回 null
        if (!moreData || moreData.length === 0) {
          console.log('[KLineChart] ✅ 无更多数据返回');
          return null;
        }

        console.log('[KLineChart] ✅ 返回数据', moreData.length, '条');
        return moreData;
      };

      console.log('[KLineChart] 🔧 注册 loadDataCallback');
      chartInstance.current.setLoadDataCallback(loadDataCallback);
    }, 100);

    // 清理函数
    return () => {
      clearTimeout(timer);
      if (chartInstance.current) {
        console.log('[KLineChart] 🗑️ 卸载 loadDataCallback');
        chartInstance.current.setLoadDataCallback(null);
      }
    };
  }, [mode, sessionId]); // 仅依赖 mode 和 sessionId

  // Effect 2: 初始数据加载
  useEffect(() => {
    if (mode === 'backtest' && sessionId) {
      loadInitialData(sessionId);
    } else if (mode === 'static' && initialKlines.length > 0) {
      setKlines(initialKlines);
      earliestTs.current = initialKlines[0]?.timestamp ?? null;
      setStatus('idle');
    }
    // realtime 模式预留
  }, [mode, sessionId]);

  // Effect 3: 数据同步到图表
  useEffect(() => {
    if (!chartInstance.current || klines.length === 0) return;

    // 首次加载使用 applyNewData
    const chartData = toChartFormat(klines);
    chartInstance.current.applyNewData(chartData);
  }, [klines]);

  // Effect 4: 交易标记更新
  useEffect(() => {
    if (!chartInstance.current) return;
    drawTradeMarkers(chartInstance.current, trades, tradesById, closeByOpenId, activeTradeId);
  }, [trades, tradesById, closeByOpenId, activeTradeId, drawTradeMarkers]);

  // Effect 5: 恢复保存的绘图
  useEffect(() => {
    if (!chartInstance.current || !symbol) return;

    try {
      const raw = localStorage.getItem(`kline-overlays-${symbol}`);
      if (!raw) return;

      // 大小验证
      if (raw.length > 200_000) {
        localStorage.removeItem(`kline-overlays-${symbol}`);
        console.warn('绘图数据异常，已清理');
        return;
      }

      const data = JSON.parse(raw);

      // 结构验证
      if (!Array.isArray(data)) {
        localStorage.removeItem(`kline-overlays-${symbol}`);
        return;
      }

      const restoredIds: string[] = [];

      for (const item of data) {
        // 验证必要字段
        if (!item.name || !item.points || !Array.isArray(item.points)) {
          continue;
        }

        const id = chartInstance.current.createOverlay({
          name: item.name,
          points: item.points,
          styles: item.styles,
          extendData: item.extendData,
        });

        if (id) {
          restoredIds.push(id);
        }
      }

      setOverlays(restoredIds);
    } catch (error) {
      console.error('恢复绘图数据失败:', error);
      // 数据损坏时清理
      localStorage.removeItem(`kline-overlays-${symbol}`);
    }
  }, [symbol]); // 仅在 symbol 变化时执行

  // ==================== UI Components ====================

  const LoadingOverlay = () => (
    <div
      className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10"
      aria-busy="true"
      aria-label="正在加载K线数据"
    >
      <div className="flex flex-col items-center gap-2">
        <div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
        <p className="text-sm text-muted-foreground">正在加载K线数据...</p>
      </div>
    </div>
  );

  const LoadingIndicator = () => (
    <div
      className="absolute top-4 left-4 bg-black/70 text-white px-3 py-1 rounded-md flex items-center gap-2 z-20"
      aria-busy={isFetchingMore}
      aria-label="正在加载更多数据"
    >
      <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      <span className="text-xs">加载历史数据中...</span>
    </div>
  );

  const ErrorOverlay = () => (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center bg-background z-20"
      role="alert"
      aria-live="assertive"
      aria-labelledby="error-title"
      aria-describedby="error-desc"
    >
      <svg className="w-12 h-12 text-red-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p id="error-title" className="text-red-500 font-semibold text-lg mb-2">加载失败</p>
      <p id="error-desc" className="text-sm text-muted-foreground mb-4">{error}</p>
      <button
        onClick={() => sessionId && loadInitialData(sessionId)}
        className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 flex items-center gap-2"
        aria-label="重新加载K线数据"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        重试
      </button>
    </div>
  );

  const DrawingToolbar = () => (
    <div className="flex items-center gap-2 mb-2 p-2 bg-card rounded-lg border shadow-sm">
      <TooltipProvider>
        <div className="flex gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant={activeTool === 'line' ? 'default' : 'outline'}
                onClick={() => handleToolSelect('line')}
                aria-label="绘制趋势线"
                aria-pressed={activeTool === 'line'}
                className="h-10 w-10 p-0"
              >
                <TrendingUp className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>趋势线</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant={activeTool === 'rect' ? 'default' : 'outline'}
                onClick={() => handleToolSelect('rect')}
                aria-label="绘制矩形"
                aria-pressed={activeTool === 'rect'}
                className="h-10 w-10 p-0"
              >
                <Square className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>矩形</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="sm"
                variant={activeTool === 'text' ? 'default' : 'outline'}
                onClick={() => handleToolSelect('text')}
                aria-label="添加文本标注"
                aria-pressed={activeTool === 'text'}
                className="h-10 w-10 p-0"
              >
                <Type className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p>文本标注</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>

      {overlays.length > 0 && (
        <>
          <div className="h-4 w-px bg-border" />
          <Button
            size="sm"
            variant="ghost"
            onClick={handleClearAll}
            aria-label="清除所有绘图"
            className="h-10 text-xs"
          >
            清除全部
          </Button>
        </>
      )}

      <div className="ml-auto text-xs text-muted-foreground hidden sm:block">
        {activeTool ? '点击图表开始绘制' : '选择工具开始绘图'}
      </div>
    </div>
  );

  // ==================== Render ====================

  return (
    <div className={cn("relative w-full flex flex-col", className)}>
      {/* 绘图工具栏 */}
      <DrawingToolbar />

      {/* K线图表 */}
      <div ref={chartRef} className="w-full" style={{ height: typeof height === 'number' ? `${height}px` : height }} />

      {/* 覆盖层 */}
      {status === 'loading' && <LoadingOverlay />}
      {isFetchingMore && <LoadingIndicator />}
      {status === 'error' && <ErrorOverlay />}
    </div>
  );
}
