'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, LineChart, Line, XAxis, YAxis } from 'recharts';

async function fetchDailyStats() {
  const res = await fetch('http://localhost:8000/api/statistics/daily');
  return res.json();
}

async function fetchWeeklyStats() {
  const res = await fetch('http://localhost:8000/api/statistics/weekly');
  return res.json();
}

const COLORS = ['hsl(var(--primary))', 'hsl(var(--secondary))', 'hsl(142 76% 36%)', 'hsl(346 87% 43%)'];

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<'daily' | 'weekly'>('daily');

  const { data: dailyStats } = useQuery({ queryKey: ['daily-stats'], queryFn: fetchDailyStats });
  const { data: weeklyStats } = useQuery({ queryKey: ['weekly-stats'], queryFn: fetchWeeklyStats });

  const stats = period === 'daily' ? dailyStats : weeklyStats;
  const strategyData = stats?.strategy_comparison || [];
  const winRateData = stats?.win_rate_trend || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">统计分析</h1>
        <div className="flex gap-2">
          <Button
            variant={period === 'daily' ? 'default' : 'outline'}
            onClick={() => setPeriod('daily')}
          >
            日统计
          </Button>
          <Button
            variant={period === 'weekly' ? 'default' : 'outline'}
            onClick={() => setPeriod('weekly')}
          >
            周统计
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">策略对比</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={strategyData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                label
              >
                {strategyData.map((_: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">胜率趋势</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={winRateData}>
              <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }} />
              <Line type="monotone" dataKey="win_rate" stroke="hsl(var(--primary))" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">关键指标</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-muted-foreground">总交易次数</p>
            <p className="text-2xl font-bold">{stats?.total_trades || 0}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">盈利交易</p>
            <p className="text-2xl font-bold text-green-500">{stats?.winning_trades || 0}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">亏损交易</p>
            <p className="text-2xl font-bold text-red-500">{stats?.losing_trades || 0}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">平均盈亏</p>
            <p className="text-2xl font-bold">${stats?.avg_pnl?.toFixed(2) || '0.00'}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}
