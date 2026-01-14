'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, DollarSign, Target } from 'lucide-react';
import { StatCard } from '@/components/StatCard';
import { Card } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import apiClient from '@/lib/api-client';

async function fetchStats() {
  const { data } = await apiClient.get('/api/statistics/daily');
  return data;
}

async function fetchTrades() {
  const { data } = await apiClient.get('/api/trades?limit=10');
  return data;
}

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
    }
  }, [router]);

  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: fetchStats });
  const { data: trades } = useQuery({ queryKey: ['trades'], queryFn: fetchTrades });

  const chartData = stats?.pnl_history || [];

  return (
    <div className="space-y-6">
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

      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">最近交易</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>时间</TableHead>
              <TableHead>交易对</TableHead>
              <TableHead>方向</TableHead>
              <TableHead>价格</TableHead>
              <TableHead>数量</TableHead>
              <TableHead className="text-right">盈亏</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades?.map((trade: any) => (
              <TableRow key={trade.id}>
                <TableCell>{new Date(trade.timestamp).toLocaleString()}</TableCell>
                <TableCell>{trade.symbol}</TableCell>
                <TableCell>
                  <span className={trade.side === 'buy' ? 'text-trading-up' : 'text-trading-down'}>
                    {trade.side.toUpperCase()}
                  </span>
                </TableCell>
                <TableCell className="font-mono tabular-nums">${trade.price?.toFixed(2)}</TableCell>
                <TableCell className="font-mono tabular-nums">{trade.amount?.toFixed(4)}</TableCell>
                <TableCell className={`text-right font-mono tabular-nums ${trade.pnl > 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                  ${trade.pnl?.toFixed(2)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
