'use client';

import { useEffect } from 'react';
import { useWebSocketContext } from '@/context/WebSocketContext';
import { useAuth } from '@/context/AuthContext';
import { Card } from '@/components/ui/card';
import { Activity, TrendingUp, AlertCircle } from 'lucide-react';
import { StatCard } from '@/components/StatCard';
import { DecisionPanel } from '@/components/DecisionPanel';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Legend } from 'recharts';

export default function MonitorPage() {
  const { requireAuth } = useAuth();
  const { data, isConnected } = useWebSocketContext();

  useEffect(requireAuth, [requireAuth]);

  const indicators = data.indicators || [];
  const position = data.position;
  const trend = data.trend;
  const ticker = data.ticker;

  const radarData = indicators.map((ind: any) => ({
    indicator: ind.name,
    value: ind.value,
    fullMark: 100,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">实时监控</h1>
        <div className="flex items-center gap-2">
          <div className={`h-3 w-3 rounded-full ${isConnected ? 'bg-trading-up' : 'bg-trading-down'} animate-pulse`} />
          <span className="text-sm text-muted-foreground">
            {isConnected ? '已连接' : '未连接'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          title="当前价格"
          value={`$${ticker?.last?.toFixed(2) || '0.00'}`}
          icon={TrendingUp}
          trend={ticker?.change_24h}
        />
        <StatCard
          title="持仓数量"
          value={position?.amount?.toFixed(4) || '0.0000'}
          icon={Activity}
        />
        <StatCard
          title="未实现盈亏"
          value={`$${position?.unrealized_pnl?.toFixed(2) || '0.00'}`}
          icon={AlertCircle}
          trend={position?.pnl_percent}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">技术指标</h2>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="hsl(var(--border))" />
              <PolarAngleAxis dataKey="indicator" stroke="hsl(var(--muted-foreground))" />
              <PolarRadiusAxis stroke="hsl(var(--muted-foreground))" />
              <Radar name="指标值" dataKey="value" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.3} />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">市场趋势</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
              <span className="text-sm font-medium">趋势方向</span>
              <span className={`text-lg font-bold ${
                trend?.direction === 'up' ? 'text-trading-up' :
                trend?.direction === 'down' ? 'text-trading-down' : 'text-muted-foreground'
              }`}>
                {trend?.direction === 'up' ? '↑ 上涨' :
                 trend?.direction === 'down' ? '↓ 下跌' : '→ 震荡'}
              </span>
            </div>
            <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
              <span className="text-sm font-medium">趋势强度</span>
              <span className="text-lg font-bold font-mono tabular-nums">{trend?.strength?.toFixed(1) || '0.0'}%</span>
            </div>
            <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
              <span className="text-sm font-medium">波动率</span>
              <span className="text-lg font-bold font-mono tabular-nums">{trend?.volatility?.toFixed(2) || '0.00'}%</span>
            </div>
          </div>
        </Card>
      </div>

      <DecisionPanel decision={data.decision} />
    </div>
  );
}
