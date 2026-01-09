import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

interface Position {
  symbol: string;
  side: string | null;
  amount: number;
  entry_price: number | null;
  current_price: number | null;
  unrealized_pnl: number | null;
  leverage: number | null;
  entry_time: string | null;
  updated_at: string | null;
}

export function useCurrentPosition(symbol?: string) {
  return useQuery({
    queryKey: ['position', 'current', symbol],
    queryFn: async () => {
      const { data } = await apiClient.get<Position | null>('/api/positions/current', {
        params: symbol ? { symbol } : undefined,
      });
      return data;
    },
    refetchInterval: 5000, // 5秒刷新
  });
}
