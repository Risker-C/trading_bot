'use client';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useMemo } from 'react';

interface StrategyConfig {
  name: string;
  weight: number;
}

interface WeightBalancePanelProps {
  strategies: StrategyConfig[];
  onAutoBalance: () => void;
}

export function WeightBalancePanel({ strategies, onAutoBalance }: WeightBalancePanelProps) {
  const totalWeight = useMemo(
    () => strategies.reduce((sum, s) => sum + s.weight, 0),
    [strategies]
  );

  const isValid = useMemo(
    () => Math.abs(totalWeight - 100) < 0.01,
    [totalWeight]
  );

  return (
    <div className="flex items-center justify-between p-3 border rounded-lg bg-muted/30">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">总权重：</span>
        <Badge
          variant={isValid ? "default" : "destructive"}
          className={isValid ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-green-200 dark:border-green-800" : ""}
        >
          {totalWeight.toFixed(1)}%
        </Badge>
        {!isValid && (
          <span className="text-xs text-destructive">
            权重总和必须为 100%
          </span>
        )}
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onAutoBalance}
        disabled={strategies.length === 0}
      >
        均分权重
      </Button>
    </div>
  );
}
