'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

const AVAILABLE_STRATEGIES = [
  { value: 'bollinger_breakthrough', label: 'Bollinger Breakthrough' },
  { value: 'bollinger_trend', label: 'Bollinger Trend' },
  { value: 'rsi_divergence', label: 'RSI Divergence' },
  { value: 'macd_cross', label: 'MACD Cross' },
  { value: 'ema_cross', label: 'EMA Cross' },
  { value: 'kdj_cross', label: 'KDJ Cross' },
  { value: 'volume_breakout', label: 'Volume Breakout' },
  { value: 'grid', label: 'Grid' },
  { value: 'composite_score', label: 'Composite Score' },
  { value: 'multi_timeframe', label: 'Multi Timeframe' },
  { value: 'adx_trend', label: 'ADX Trend' },
];

interface StrategyMultiSelectorProps {
  selected: string[];
  onToggle: (name: string) => void;
}

export function StrategyMultiSelector({ selected, onToggle }: StrategyMultiSelectorProps) {
  return (
    <div className="space-y-2">
      <Label>选择策略</Label>
      <div className="grid grid-cols-2 gap-2">
        {AVAILABLE_STRATEGIES.map((strategy) => (
          <div key={strategy.value} className="flex items-center space-x-2">
            <Checkbox
              id={strategy.value}
              checked={selected.includes(strategy.value)}
              onCheckedChange={() => onToggle(strategy.value)}
            />
            <label
              htmlFor={strategy.value}
              className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
            >
              {strategy.label}
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
