'use client';

import { StatCard } from './StatCard';
import { TrendingUp, DollarSign, Activity } from 'lucide-react';

interface MarketOverviewProps {
  ticker?: {
    symbol: string;
    last: number;
    bid: number;
    ask: number;
    volume: number;
    change_24h: number;
    high_24h: number;
    low_24h: number;
    stale: boolean;
  };
}

export function MarketOverview({ ticker }: MarketOverviewProps) {
  if (!ticker) {
    return (
      <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700/50">
        <h2 className="text-xl font-bold text-white mb-4">市场概览</h2>
        <p className="text-gray-400">加载中...</p>
      </div>
    );
  }

  const spread = ticker.ask - ticker.bid;
  const spreadPercent = (spread / ticker.last) * 100;
  const rangePosition = ticker.high_24h > ticker.low_24h
    ? ((ticker.last - ticker.low_24h) / (ticker.high_24h - ticker.low_24h)) * 100
    : 50;

  return (
    <div className="bg-gray-800/50 backdrop-blur-sm rounded-xl p-6 border border-gray-700/50">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-white">市场概览 - {ticker.symbol}</h2>
        {ticker.stale && (
          <span className="text-xs text-yellow-500 flex items-center gap-1">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-500"></span>
            </span>
            数据延迟
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="当前价格"
          value={`$${ticker.last.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={TrendingUp}
          trend={ticker.change_24h}
        />
        <StatCard
          title="买价"
          value={`$${ticker.bid.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={DollarSign}
        />
        <StatCard
          title="卖价"
          value={`$${ticker.ask.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={DollarSign}
        />
        <StatCard
          title="买卖价差"
          value={`$${spread.toFixed(2)} (${spreadPercent.toFixed(3)}%)`}
          icon={Activity}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="24h 成交量"
          value={ticker.volume.toLocaleString('en-US', { maximumFractionDigits: 2 })}
          icon={Activity}
        />
        <StatCard
          title="24h 最高"
          value={`$${ticker.high_24h.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={TrendingUp}
        />
        <StatCard
          title="24h 最低"
          value={`$${ticker.low_24h.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          icon={TrendingUp}
        />
      </div>

      {/* Price Range Visualization */}
      <div className="mt-6">
        <div className="flex justify-between text-xs text-gray-400 mb-2">
          <span>24h 最低</span>
          <span>24h 最高</span>
        </div>
        <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className="absolute h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500"
            style={{ width: '100%' }}
          />
          <div
            className="absolute h-full w-1 bg-white shadow-lg"
            style={{ left: `${rangePosition}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>${ticker.low_24h.toFixed(2)}</span>
          <span>${ticker.high_24h.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}
