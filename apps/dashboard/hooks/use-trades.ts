import { useQuery } from '@tanstack/react-query';
import apiClient from '@/lib/api-client';

interface Trade {
  id: number;
  symbol: string;
  side: string | null;
  action: string | null;
  amount: number;
  price: number;
  pnl: number | null;
  pnl_percent: number | null;
  strategy: string | null;
  reason: string | null;
  status: string | null;
  created_at: string;
}

export function useTrades(params?: {
  limit?: number;
  offset?: number;
  strategy?: string;
}) {
  return useQuery({
    queryKey: ['trades', params],
    queryFn: async () => {
      const { data } = await apiClient.get<Trade[]>('/api/trades', { params });
      return data;
    },
    refetchInterval: 30000, // 30秒自动刷新
  });
}
