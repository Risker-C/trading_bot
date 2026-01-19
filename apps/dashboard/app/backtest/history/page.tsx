'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Link from 'next/link';
import axios from 'axios';

interface SessionSummary {
  session_id: string;
  created_at: number;
  updated_at: number;
  status: string;
  symbol: string;
  timeframe: string;
  start_ts: number;
  end_ts: number;
  strategy_name: string;
  strategy_params: string | null;
  total_trades: number | null;
  win_rate: number | null;
  total_return: number | null;
  max_drawdown: number | null;
  sharpe: number | null;
}

export default function BacktestHistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);

  // Filters
  const [strategyName, setStrategyName] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const loadSessions = useCallback(async (cursor: string | null = null, append: boolean = false) => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (cursor) params.append('cursor', cursor);
      params.append('limit', '50');
      params.append('sort_by', sortBy);
      params.append('sort_dir', sortDir);
      if (strategyName) params.append('strategy_name', strategyName);

      const response = await axios.get(`${apiUrl}/api/backtests/sessions?${params.toString()}`);
      const data = response.data;

      if (append) {
        setSessions(prev => [...prev, ...data.data]);
      } else {
        setSessions(data.data);
      }

      setNextCursor(data.next_cursor);
      setHasMore(data.has_more);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [apiUrl, sortBy, sortDir, strategyName]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleLoadMore = () => {
    if (nextCursor && !loading) {
      loadSessions(nextCursor, true);
    }
  };

  const handleSearch = () => {
    loadSessions();
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  const formatPercent = (value: number | null) => {
    if (value === null) return '-';
    return `${(value * 100).toFixed(2)}%`;
  };

  const formatNumber = (value: number | null, decimals: number = 2) => {
    if (value === null) return '-';
    return value.toFixed(decimals);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">回测历史</h1>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <Label>策略名称</Label>
            <Input
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              placeholder="输入策略名称"
            />
          </div>

          <div>
            <Label>排序字段</Label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full p-2 border rounded bg-background text-foreground"
            >
              <option value="created_at">创建时间</option>
              <option value="total_return">总收益率</option>
              <option value="sharpe">夏普比率</option>
              <option value="max_drawdown">最大回撤</option>
              <option value="win_rate">胜率</option>
            </select>
          </div>

          <div>
            <Label>排序方向</Label>
            <select
              value={sortDir}
              onChange={(e) => setSortDir(e.target.value)}
              className="w-full p-2 border rounded bg-background text-foreground"
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </div>

          <div className="flex items-end">
            <Button onClick={handleSearch} className="w-full">
              搜索
            </Button>
          </div>
        </div>
      </Card>

      {/* Error Message */}
      {error && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-red-600">{error}</p>
        </Card>
      )}

      {/* Sessions Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  创建时间
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  策略
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  交易对
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  周期
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  交易次数
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  胜率
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  总收益率
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  最大回撤
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  夏普比率
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-card divide-y divide-border">
              {loading && sessions.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-muted-foreground">
                    <div className="flex justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                    <p className="mt-2">加载中...</p>
                  </td>
                </tr>
              ) : sessions.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-muted-foreground">
                    暂无回测记录
                  </td>
                </tr>
              ) : (
                sessions.map((session) => (
                  <tr key={session.session_id} className="hover:bg-muted/50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                      {formatDate(session.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                      {session.strategy_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                      {session.symbol}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                      {session.timeframe}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right">
                      {session.total_trades ?? '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right">
                      {formatPercent(session.win_rate)}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                      session.total_return && session.total_return > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                    }`}>
                      {formatPercent(session.total_return)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600 dark:text-red-400 text-right">
                      {formatPercent(session.max_drawdown)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground text-right">
                      {formatNumber(session.sharpe)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                      <Link
                        href={`/backtest/history/${session.session_id}`}
                        className="text-primary hover:text-primary/80"
                      >
                        查看详情
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Load More */}
        {hasMore && (
          <div className="px-6 py-4 border-t border-border flex justify-center">
            <Button
              onClick={handleLoadMore}
              disabled={loading}
              variant="outline"
            >
              {loading ? '加载中...' : '加载更多'}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
