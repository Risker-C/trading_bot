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
          name: 'simpleTag',
          points: [
            {
              timestamp: trade.ts * 1000,
              value: trade.price,
            }
          ],
          text: trade.action === 'open' ? (trade.side === 'long' ? 'B' : 'S') : 'C',
          styles: {
            point: {
              color: trade.action === 'open'
                ? (trade.side === 'long' ? '#22c55e' : '#ef4444')
                : '#6b7280',
              borderColor: isActive ? '#3b82f6' : 'transparent',
              borderSize: isActive ? 2 : 0,
              radius: isActive ? 6 : 4,
            },
            text: {
              color: '#ffffff',
              size: 12,
              family: 'Arial',
              weight: 'bold',
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
