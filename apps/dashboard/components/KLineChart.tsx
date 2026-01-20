'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { init, dispose } from 'klinecharts';
import apiClient from '@/lib/api-client';
import { cn } from '@/lib/utils';

// ==================== Types ====================

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

  // ==================== Refs ====================
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);
  const hasMore = useRef(true);
  const earliestTs = useRef<number | null>(null);
  const isInitialized = useRef(false);

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
      setStatus('idle');
    } catch (err) {
      setError(parseError(err));
      setStatus('error');
    }
  };

  // 使用 useCallback 避免闭包过期问题
  const loadMore = useCallback(async (): Promise<any[]> => {
    if (!sessionId || !earliestTs.current || !hasMore.current || isFetchingMore) {
      return [];
    }

    setIsFetchingMore(true);

    try {
      const res = await apiClient.get(
        `/api/backtests/sessions/${sessionId}/klines?limit=1000&before=${earliestTs.current}`
      );
      const newData = res.data || [];

      if (newData.length === 0) {
        hasMore.current = false;
        return [];
      }

      // 确保新数据升序排序
      const sortedNewData = newData.sort((a: KLineData, b: KLineData) => a.timestamp - b.timestamp);

      // 去重合并
      setKlines(prevKlines => {
        const merged = mergeKlines(sortedNewData, prevKlines);
        earliestTs.current = merged[0]?.timestamp ?? earliestTs.current;
        return merged;
      });

      // 转换格式后返回给图表 applyMoreData
      return toChartFormat(sortedNewData);
    } catch (err) {
      console.error('Failed to load more klines:', err);
      return [];
    } finally {
      setIsFetchingMore(false);
    }
  }, [sessionId, isFetchingMore]); // 添加依赖

  // ==================== Trade Markers ====================

  const drawTradeMarkers = (chart: any, tradesList: Trade[], activeId?: number | null) => {
    if (!chart || !tradesList || tradesList.length === 0) return;

    // 清除旧标记
    chart.removeOverlay();

    // 1. 绘制配对交易的连接线
    tradesList.forEach(trade => {
      if (trade.action === 'close' && trade.open_trade_id) {
        const openTrade = tradesList.find(t => t.id === trade.open_trade_id);
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
                color: (trade.pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444',
                dashedValue: [4, 4]
              }
            }
          });
        }
      }
    });

    // 2. 绘制交易点标记
    tradesList.forEach(trade => {
      const pairedTrade = trade.action === 'close'
        ? tradesList.find(t => t.id === trade.open_trade_id)
        : tradesList.find(t => t.open_trade_id === trade.id && t.action === 'close');

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
        symbolColor = trade.side === 'long' ? '#22c55e' : '#ef4444';
      } else {
        symbolType = 'circle';
        symbolColor = (trade.pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444';
      }

      chart.createOverlay({
        name: 'simpleAnnotation',
        points: [{ timestamp: trade.ts * 1000, value: trade.price }],
        styles: {
          symbol: {
            type: symbolType,
            size: isPaired ? 10 : 8,
            color: symbolColor,
            activeColor: '#3b82f6',
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
        extendData: { id: trade.id, info: tradeInfo },
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
  };

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

  // Effect 1.5: 注册增量加载回调（依赖 loadMore）
  useEffect(() => {
    if (!chartInstance.current || mode !== 'backtest' || !sessionId) return;

    chartInstance.current.setLoadDataCallback?.(async (params: any) => {
      const moreData = await loadMore();
      if (moreData && moreData.length > 0) {
        return moreData;
      }
      return [];
    });
  }, [mode, sessionId, loadMore]); // 依赖 loadMore

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
    drawTradeMarkers(chartInstance.current, trades, activeTradeId);
  }, [trades, activeTradeId, strategyName]);

  // ==================== UI Components ====================

  const LoadingOverlay = () => (
    <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm z-10">
      <div className="flex flex-col items-center gap-2">
        <div className="w-8 h-8 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
        <p className="text-sm text-muted-foreground">正在加载K线数据...</p>
      </div>
    </div>
  );

  const LoadingIndicator = () => (
    <div className="absolute top-4 left-4 bg-black/70 text-white px-3 py-1 rounded-md flex items-center gap-2 z-20">
      <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
      <span className="text-xs">加载历史数据中...</span>
    </div>
  );

  const ErrorOverlay = () => (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-background z-20">
      <svg className="w-12 h-12 text-red-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p className="text-red-500 mb-4">{error}</p>
      <button
        onClick={() => sessionId && loadInitialData(sessionId)}
        className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        重试
      </button>
    </div>
  );

  // ==================== Render ====================

  return (
    <div className={cn("relative w-full", className)} style={{ height }}>
      <div ref={chartRef} className="w-full h-full" />

      {status === 'loading' && <LoadingOverlay />}
      {isFetchingMore && <LoadingIndicator />}
      {status === 'error' && <ErrorOverlay />}
    </div>
  );
}
