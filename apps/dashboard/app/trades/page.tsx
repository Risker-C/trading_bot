'use client';

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/context/AuthContext';
import { Card } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import apiClient from '@/lib/api-client';
import dayjs from 'dayjs';

async function fetchTrades(limit: number, offset: number) {
  const { data } = await apiClient.get(`/api/trades?limit=${limit}&offset=${offset}`);
  return data;
}

export default function TradesPage() {
  const { isAuthenticated, requireAuth } = useAuth();
  const [page, setPage] = useState(0);
  const limit = 20;

  useEffect(requireAuth, [requireAuth]);

  const { data: trades, isLoading } = useQuery({
    queryKey: ['trades', page],
    queryFn: () => fetchTrades(limit, page * limit),
    enabled: isAuthenticated
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">交易历史</h1>
      </div>

      <Card className="p-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>时间</TableHead>
              <TableHead>交易对</TableHead>
              <TableHead>方向</TableHead>
              <TableHead>价格</TableHead>
              <TableHead>数量</TableHead>
              <TableHead>手续费</TableHead>
              <TableHead className="text-right">盈亏</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  加载中...
                </TableCell>
              </TableRow>
            ) : trades?.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground">
                  暂无交易记录
                </TableCell>
              </TableRow>
            ) : (
              trades?.map((trade: any) => (
                <TableRow key={trade.id} className="hover:bg-muted/50 transition-colors">
                  <TableCell>{dayjs(trade.created_at).format('YYYY-MM-DD HH:mm:ss')}</TableCell>
                  <TableCell className="font-medium">{trade.symbol}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      trade.side === 'buy'
                        ? 'bg-trading-up/10 text-trading-up'
                        : 'bg-trading-down/10 text-trading-down'
                    }`}>
                      {trade.side === 'buy' ? '买入' : '卖出'}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono tabular-nums">${trade.price?.toFixed(2)}</TableCell>
                  <TableCell className="font-mono tabular-nums">{trade.amount?.toFixed(4)}</TableCell>
                  <TableCell className="font-mono tabular-nums">${trade.fee?.toFixed(2) || '0.00'}</TableCell>
                  <TableCell className={`text-right font-semibold font-mono tabular-nums ${
                    trade.pnl > 0 ? 'text-trading-up' : trade.pnl < 0 ? 'text-trading-down' : 'text-muted-foreground'
                  }`}>
                    {trade.pnl > 0 ? '+' : ''}${trade.pnl?.toFixed(2)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        <div className="flex items-center justify-between mt-4">
          <Button
            variant="outline"
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            上一页
          </Button>
          <span className="text-sm text-muted-foreground">
            第 {page + 1} 页
          </span>
          <Button
            variant="outline"
            onClick={() => setPage(p => p + 1)}
            disabled={!trades || trades.length < limit}
          >
            下一页
          </Button>
        </div>
      </Card>
    </div>
  );
}
