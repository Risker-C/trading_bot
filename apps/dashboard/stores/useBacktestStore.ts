import { create } from 'zustand';

interface BacktestState {
  status: 'idle' | 'running' | 'finished';
  progress: number;
  currentSessionId: string | null;
  params: {
    symbol: string;
    interval: string;
    dateRange: [Date | null, Date | null];
    capital: number;
    strategyName: string;
    strategyParams: Record<string, any>;
  };
  activeTradeId: number | null;
  setStatus: (status: 'idle' | 'running' | 'finished') => void;
  setProgress: (progress: number) => void;
  setCurrentSessionId: (id: string | null) => void;
  setParams: (params: Partial<BacktestState['params']>) => void;
  setActiveTradeId: (id: number | null) => void;
  reset: () => void;
}

const initialParams = {
  symbol: 'BTC/USDT:USDT',
  interval: '15m',
  dateRange: [null, null] as [Date | null, Date | null],
  capital: 10000,
  strategyName: 'bollinger_trend',
  strategyParams: {},
};

export const useBacktestStore = create<BacktestState>((set) => ({
  status: 'idle',
  progress: 0,
  currentSessionId: null,
  params: initialParams,
  activeTradeId: null,
  setStatus: (status) => set({ status }),
  setProgress: (progress) => set({ progress }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  setParams: (params) => set((state) => ({ params: { ...state.params, ...params } })),
  setActiveTradeId: (id) => set({ activeTradeId: id }),
  reset: () => set({ status: 'idle', progress: 0, currentSessionId: null, params: initialParams, activeTradeId: null }),
}));
