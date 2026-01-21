'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import KLineChart from '@/components/KLineChart';
import AIAnalysisPanel from '@/components/backtest/AIAnalysisPanel';
import axios from 'axios';

interface SessionDetail {
  session_id: string;
  created_at: number;
  status: string;
  symbol: string;
  timeframe: string;
  start_ts: number;
  end_ts: number;
  strategy_name: string;
  strategy_params: string | null;
  initial_capital: number;
}

interface Metrics {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  total_return: number;
  max_drawdown: number;
  sharpe: number;
  profit_factor: number;
  expectancy: number;
  avg_win: number;
  avg_loss: number;
}

interface Trade {
  id: number;
  ts: number;
  symbol: string;
  side: string;
  action: string;
  qty: number;
  price: number;
  fee: number;
  pnl: number | null;
  pnl_pct: number | null;
  reason: string | null;
}

export default function BacktestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load session info
        const sessionRes = await axios.get(`${apiUrl}/api/backtests/sessions/${sessionId}`);
        setSession(sessionRes.data);

        // Load metrics
        const metricsRes = await axios.get(`${apiUrl}/api/backtests/sessions/${sessionId}/metrics`);
        setMetrics(metricsRes.data);

        // Load trades
        const tradesRes = await axios.get(`${apiUrl}/api/backtests/sessions/${sessionId}/trades?limit=1000`);
        setTrades(tradesRes.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || '加载失败');
      } finally {
        setLoading(false);
      }
    };

    if (sessionId) {
      loadData();
    }
  }, [sessionId, apiUrl]);

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(2)}%`;
  };

  const formatNumber = (value: number, decimals: number = 2) => {
    return value.toFixed(decimals);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">加载中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card className="p-6 bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
          <p className="text-red-600 dark:text-red-400">{error}</p>
          <Button onClick={() => router.back()} className="mt-4">
            返回
          </Button>
        </Card>
      </div>
    );
  }

  if (!session || !metrics) {
    return (
      <div className="p-6">
        <Card className="p-6">
          <p className="text-muted-foreground">未找到回测记录</p>
          <Button onClick={() => router.back()} className="mt-4">
            返回
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">回测详情</h1>
          <p className="text-sm text-gray-500 mt-1">
            {session.strategy_name} - {session.symbol} - {session.timeframe}
          </p>
        </div>
        <Button onClick={() => router.back()} variant="outline">
          返回列表
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-sm text-gray-500">总收益率</p>
          <p className={`text-2xl font-bold mt-1 ${metrics.total_return > 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPercent(metrics.total_return)}
          </p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">夏普比率</p>
          <p className="text-2xl font-bold mt-1">{formatNumber(metrics.sharpe)}</p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">最大回撤</p>
          <p className="text-2xl font-bold mt-1 text-red-600">{formatPercent(metrics.max_drawdown)}</p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">胜率</p>
          <p className="text-2xl font-bold mt-1">{formatPercent(metrics.win_rate)}</p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">交易次数</p>
          <p className="text-2xl font-bold mt-1">{metrics.total_trades}</p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">盈亏比</p>
          <p className="text-2xl font-bold mt-1">{formatNumber(metrics.profit_factor)}</p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">期望收益</p>
          <p className="text-2xl font-bold mt-1">${formatNumber(metrics.expectancy)}</p>
        </Card>

        <Card className="p-4">
          <p className="text-sm text-gray-500">总盈亏</p>
          <p className={`text-2xl font-bold mt-1 ${metrics.total_pnl > 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${formatNumber(metrics.total_pnl)}
          </p>
        </Card>
      </div>

      {/* K-Line Chart */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">K线图表</h2>
        <KLineChart
          mode="backtest"
          sessionId={sessionId}
          trades={trades.map(t => ({
            ...t,
            reason: t.reason ?? undefined,
            pnl: t.pnl ?? undefined,
            pnl_pct: t.pnl_pct ?? undefined
          }))}
          strategyName={session.strategy_name}
        />
      </Card>

      {/* AI Analysis Panel */}
      <AIAnalysisPanel sessionId={sessionId} />

      {/* Trades Table */}
      <Card className="overflow-hidden">
        <div className="p-6 border-b border-border">
          <h2 className="text-xl font-semibold">交易明细</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  时间
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  方向
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  操作
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  数量
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  价格
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  金额(USDT)
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  手续费
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  盈亏
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  盈亏%
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  原因
                </th>
              </tr>
            </thead>
            <tbody className="bg-card divide-y divide-border">
              {trades.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-muted-foreground">
                    暂无交易记录
                  </td>
                </tr>
              ) : (
                trades.map((trade) => (
                  <tr key={trade.id} className="hover:bg-muted/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                      {formatDate(trade.ts)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        trade.side === 'long'
                          ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                          : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
                      }`}>
                        {trade.side === 'long' ? '做多' : '做空'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        trade.action === 'open'
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
                          : 'bg-muted text-muted-foreground'
                      }`}>
                        {trade.action === 'open' ? '开仓' : '平仓'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right">
                      {formatNumber(trade.qty, 4)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right">
                      ${formatNumber(trade.price)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right font-mono">
                      ${formatNumber(trade.qty * trade.price)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right">
                      ${formatNumber(trade.fee)}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                      trade.pnl && trade.pnl > 0
                        ? 'text-green-600 dark:text-green-400'
                        : trade.pnl && trade.pnl < 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-foreground'
                    }`}>
                      {trade.pnl !== null ? `$${formatNumber(trade.pnl)}` : '-'}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                      trade.pnl_pct && trade.pnl_pct > 0
                        ? 'text-green-600 dark:text-green-400'
                        : trade.pnl_pct && trade.pnl_pct < 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-foreground'
                    }`}>
                      {trade.pnl_pct !== null ? formatPercent(trade.pnl_pct) : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {trade.reason || '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
