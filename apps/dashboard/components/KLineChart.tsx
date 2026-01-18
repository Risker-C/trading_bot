'use client';

import { useEffect, useRef } from 'react';
import { init, dispose } from 'klinecharts';

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
}

interface KLineChartProps {
  data: KLineData[];
  trades?: Trade[];
  activeTradeId?: number | null;
  onTradeClick?: (tradeId: number) => void;
  strategyName?: string;
}

export default function KLineChart({ data, trades = [], activeTradeId, onTradeClick, strategyName }: KLineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<any>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    chartInstance.current = init(chartRef.current);
    chartInstance.current.applyNewData(
      data.map(d => ({
        timestamp: d.timestamp * 1000,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        volume: d.volume,
      }))
    );

    if (trades.length > 0) {
      trades.forEach(trade => {
        const isActive = activeTradeId === trade.id;

        // 构建交易信息文本
        const tradeInfo = [
          `${trade.action === 'open' ? '开仓' : '平仓'} ${trade.side === 'long' ? '做多' : '做空'}`,
          `价格: ${trade.price.toFixed(2)}`,
          trade.qty ? `数量: ${trade.qty.toFixed(4)}` : '',
          trade.strategy_name ? `策略: ${trade.strategy_name}` : '',
          trade.reason ? `原因: ${trade.reason}` : '',
          trade.pnl ? `盈亏: ${trade.pnl.toFixed(2)}` : ''
        ].filter(Boolean).join('\n');

        chartInstance.current.createOverlay({
          name: 'simpleAnnotation',
          points: [
            {
              timestamp: trade.ts * 1000,
              value: trade.price,
            }
          ],
          styles: {
            symbol: {
              type: 'circle',
              size: isActive ? 8 : 6,
              color: trade.action === 'open'
                ? (trade.side === 'long' ? '#22c55e' : '#ef4444')
                : '#6b7280',
              activeColor: '#3b82f6',
              offset: [0, 0]
            }
          },
          extendData: {
            id: trade.id,
            info: tradeInfo
          },
          onMouseEnter: () => {
            if (onTradeClick) {
              // Highlight on hover
            }
          },
          onClick: () => {
            if (onTradeClick) {
              onTradeClick(trade.id);
            }
          },
        });
      });

      // 根据策略动态创建指标
      const indicatorMap: Record<string, string> = {
        'bollinger_trend': 'BOLL',
        'bollinger_breakthrough': 'BOLL',
        'macd_cross': 'MACD',
        'ema_cross': 'EMA',
        'rsi_divergence': 'RSI',
        'composite_score': 'MA',
        'multi_timeframe': 'MA',
      };

      const indicator = strategyName ? indicatorMap[strategyName] || 'MA' : 'MA';
      chartInstance.current.createIndicator(indicator, false, { id: 'candle_pane' });
    }

    return () => {
      if (chartInstance.current) {
        dispose(chartRef.current!);
        chartInstance.current = null;
      }
    };
  }, [data, trades, activeTradeId, onTradeClick]);

  return <div ref={chartRef} className="w-full h-[500px]" />;
}
