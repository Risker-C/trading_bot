'use client';

import { useEffect, useState } from 'react';

interface TickerProps {
  ticker?: {
    symbol: string;
    last: number;
    change_24h: number;
    stale: boolean;
  };
}

export function TickerDisplay({ ticker }: TickerProps) {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null);
  const [prevPrice, setPrevPrice] = useState<number | null>(null);

  useEffect(() => {
    if (ticker?.last && prevPrice !== null && ticker.last !== prevPrice) {
      setFlash(ticker.last > prevPrice ? 'up' : 'down');
      const timer = setTimeout(() => setFlash(null), 500);
      return () => clearTimeout(timer);
    }
    if (ticker?.last) {
      setPrevPrice(ticker.last);
    }
  }, [ticker?.last]);

  if (!ticker) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span>加载中...</span>
      </div>
    );
  }

  const isPositive = ticker.change_24h >= 0;
  const flashClass = flash === 'up' ? 'bg-green-500/20' : flash === 'down' ? 'bg-red-500/20' : '';

  return (
    <div className={`flex items-center gap-3 px-3 py-1.5 rounded-lg transition-colors ${flashClass}`}>
      {/* Symbol */}
      <span className="text-sm font-medium text-gray-300">{ticker.symbol}</span>

      {/* Price */}
      <span className="text-lg font-bold tabular-nums text-white">
        ${ticker.last.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>

      {/* 24h Change */}
      <span className={`text-sm font-medium tabular-nums ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
        {isPositive ? '↑' : '↓'} {Math.abs(ticker.change_24h).toFixed(2)}%
      </span>

      {/* Stale Indicator */}
      {ticker.stale && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500"></span>
        </span>
      )}
    </div>
  );
}
