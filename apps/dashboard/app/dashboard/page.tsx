'use client';

import { MetricCard } from '@/components/MetricCard';
import { TradeTable } from '@/components/tables/TradeTable';
import { useCurrentPosition } from '@/hooks/use-position';
import { DollarSign, TrendingUp, Percent, Activity } from 'lucide-react';

export default function DashboardPage() {
  const { data: position } = useCurrentPosition();

  return (
    <div className="flex min-h-screen flex-col p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Trading Dashboard</h1>
        <p className="text-muted-foreground">实时交易数据可视化</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <MetricCard
          title="当前持仓"
          value={position?.amount || 0}
          icon={<Activity className="h-4 w-4 text-muted-foreground" />}
        />
        <MetricCard
          title="入场价格"
          value={position?.entry_price ? `$${position.entry_price.toFixed(2)}` : '-'}
          icon={<DollarSign className="h-4 w-4 text-muted-foreground" />}
        />
        <MetricCard
          title="未实现盈亏"
          value={position?.unrealized_pnl ? `$${position.unrealized_pnl.toFixed(2)}` : '-'}
          trend={position?.unrealized_pnl && position.unrealized_pnl > 0 ? 'up' : 'down'}
          icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
        />
        <MetricCard
          title="杠杆"
          value={position?.leverage ? `${position.leverage}x` : '-'}
          icon={<Percent className="h-4 w-4 text-muted-foreground" />}
        />
      </div>

      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-4">交易记录</h2>
        <TradeTable />
      </div>
    </div>
  );
}
