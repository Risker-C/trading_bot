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
}

interface KLineChartProps {
  data: KLineData[];
  trades?: Trade[];
  activeTradeId?: number | null;
  onTradeClick?: (tradeId: number) => void;
}

export default function KLineChart({ data, trades = [], activeTradeId, onTradeClick }: KLineChartProps) {
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
            },
            text: {
              style: 'fill',
              size: 0,
              color: 'transparent'
            }
          },
          extendData: trade.id,
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

      chartInstance.current.createIndicator('MA', false, { id: 'candle_pane' });
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
