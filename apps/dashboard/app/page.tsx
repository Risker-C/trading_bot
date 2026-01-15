'use client';

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, DollarSign, Target } from 'lucide-react';
import { StatCard } from '@/components/StatCard';
import { Card } from '@/components/ui/card';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import apiClient from '@/lib/api-client';
import { MarketOverview } from '@/components/MarketOverview';
import { useWebSocketContext } from '@/context/WebSocketContext';
import { useAuth } from '@/context/AuthContext';

async function fetchStats() {
  const { data } = await apiClient.get('/api/statistics/daily');
  return data;
}


export default function HomePage() {
  const { isAuthenticated, requireAuth } = useAuth();
  const { data: wsData } = useWebSocketContext();

  useEffect(requireAuth, [requireAuth]);

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    enabled: isAuthenticated
  });

  const chartData = stats?.pnl_history || [];

  return (
    <div className="space-y-6">
      <MarketOverview ticker={wsData?.ticker} />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="总盈亏"
          value={`$${stats?.total_pnl?.toFixed(2) || '0.00'}`}
          icon={DollarSign}
          trend={stats?.pnl_trend}
        />
        <StatCard
          title="胜率"
          value={`${stats?.win_rate?.toFixed(1) || '0.0'}%`}
          icon={Target}
          trend={stats?.win_rate_trend}
        />
        <StatCard
          title="今日收益"
          value={`$${stats?.today_profit?.toFixed(2) || '0.00'}`}
          icon={TrendingUp}
          trend={stats?.today_trend}
        />
        <StatCard
          title="持仓状态"
          value={stats?.position_status || 'N/A'}
          icon={TrendingDown}
        />
      </div>

      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">盈亏曲线</h2>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }} />
            <Area type="monotone" dataKey="pnl" stroke="hsl(var(--primary))" fill="url(#colorPnl)" />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
