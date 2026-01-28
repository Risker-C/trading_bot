'use client';

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

interface StrategyConfig {
  name: string;
  weight: number;
}

interface WeightConfigListProps {
  strategies: StrategyConfig[];
  onUpdateWeight: (name: string, weight: number) => void;
  onRemove: (name: string) => void;
}

const STRATEGY_LABELS: Record<string, string> = {
  'bollinger_trend': 'Bollinger Trend',
  'macd_cross': 'MACD Cross',
  'ema_cross': 'EMA Cross',
  'composite_score': 'Composite Score',
  'multi_timeframe': 'Multi Timeframe',
  'adx_trend': 'ADX Trend',
  'band_limited_hedging': 'Band-Limited Hedging',
};

export function WeightConfigList({ strategies, onUpdateWeight, onRemove }: WeightConfigListProps) {
  if (strategies.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        请选择至少一个策略
      </div>
    );
  }

  return (
    <div className="space-y-2 p-4 border rounded-lg bg-muted/30">
      {strategies.map((strategy) => (
        <div
          key={strategy.name}
          className="flex items-center gap-3 py-2 border-b last:border-0"
        >
          <span className="flex-1 text-sm font-medium">
            {STRATEGY_LABELS[strategy.name] || strategy.name}
          </span>
          <div className="relative w-24">
            <Input
              type="number"
              min="0"
              max="100"
              step="0.1"
              value={strategy.weight}
              onChange={(e) => {
                const value = parseFloat(e.target.value);
                if (!isNaN(value)) {
                  onUpdateWeight(strategy.name, value);
                }
              }}
              className="w-full text-right pr-8"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-sm text-muted-foreground pointer-events-none">
              %
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRemove(strategy.name)}
            className="h-8 w-8 p-0"
            disabled={strategies.length === 1}
          >
            ✕
          </Button>
        </div>
      ))}
    </div>
  );
}
