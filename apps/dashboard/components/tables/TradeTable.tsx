'use client';

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useTrades } from '@/hooks/use-trades';

export function TradeTable() {
  const { data: trades, isLoading } = useTrades({ limit: 20 });

  if (isLoading) {
    return <div className="text-center py-8">加载中...</div>;
  }

  if (!trades || trades.length === 0) {
    return <div className="text-center py-8 text-muted-foreground">暂无交易记录</div>;
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>时间</TableHead>
            <TableHead>交易对</TableHead>
            <TableHead>方向</TableHead>
            <TableHead>价格</TableHead>
            <TableHead>数量</TableHead>
            <TableHead>盈亏</TableHead>
            <TableHead>策略</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {trades.map((trade) => (
            <TableRow key={trade.id}>
              <TableCell className="text-sm">
                {new Date(trade.created_at).toLocaleString('zh-CN')}
              </TableCell>
              <TableCell className="font-medium">{trade.symbol}</TableCell>
              <TableCell>
                <span className={trade.side === 'long' ? 'text-green-600' : 'text-red-600'}>
                  {trade.side === 'long' ? '做多' : '做空'}
                </span>
              </TableCell>
              <TableCell>{trade.price.toFixed(2)}</TableCell>
              <TableCell>{trade.amount}</TableCell>
              <TableCell>
                <span className={trade.pnl && trade.pnl > 0 ? 'text-green-600' : 'text-red-600'}>
                  {trade.pnl ? `${trade.pnl > 0 ? '+' : ''}${trade.pnl.toFixed(2)}` : '-'}
                </span>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">{trade.strategy || '-'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
