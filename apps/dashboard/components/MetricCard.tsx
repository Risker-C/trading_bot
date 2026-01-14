import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowUpIcon, ArrowDownIcon } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'neutral';
  icon?: React.ReactNode;
}

export function MetricCard({ title, value, change, trend = 'neutral', icon }: MetricCardProps) {
  const trendColor = trend === 'up' ? 'text-trading-up' : trend === 'down' ? 'text-trading-down' : 'text-muted-foreground';
  const TrendIcon = trend === 'up' ? ArrowUpIcon : trend === 'down' ? ArrowDownIcon : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold font-mono tabular-nums">{value}</div>
        {change !== undefined && (
          <p className={`text-xs ${trendColor} flex items-center mt-1 font-mono tabular-nums`}>
            {TrendIcon && <TrendIcon className="h-4 w-4 mr-1" />}
            {change > 0 ? '+' : ''}{change.toFixed(2)}%
          </p>
        )}
      </CardContent>
    </Card>
  );
}
