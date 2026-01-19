import { create } from 'zustand';

interface StrategyConfig {
  name: string;
  weight: number; // 0-100
}

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
    selectedStrategies: StrategyConfig[]; // 新增：多策略配置
  };
  activeTradeId: number | null;
  setStatus: (status: 'idle' | 'running' | 'finished') => void;
  setProgress: (progress: number) => void;
  setCurrentSessionId: (id: string | null) => void;
  setParams: (params: Partial<BacktestState['params']>) => void;
  setActiveTradeId: (id: number | null) => void;
  addStrategy: (name: string) => void;
  removeStrategy: (name: string) => void;
  updateWeight: (name: string, weight: number) => void;
  autoBalanceWeights: () => void;
  reset: () => void;
}

const initialParams = {
  symbol: 'BTC/USDT:USDT',
  interval: '15m',
  dateRange: [null, null] as [Date | null, Date | null],
  capital: 10000,
  strategyName: 'bollinger_trend',
  strategyParams: {},
  selectedStrategies: [{ name: 'bollinger_trend', weight: 100 }], // 默认单策略
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

  // 添加策略
  addStrategy: (name) => set((state) => {
    // 检查是否已存在
    if (state.params.selectedStrategies.some(s => s.name === name)) {
      return state;
    }
    return {
      params: {
        ...state.params,
        selectedStrategies: [
          ...state.params.selectedStrategies,
          { name, weight: 0 }
        ]
      }
    };
  }),

  // 移除策略
  removeStrategy: (name) => set((state) => ({
    params: {
      ...state.params,
      selectedStrategies: state.params.selectedStrategies.filter(s => s.name !== name)
    }
  })),

  // 更新权重
  updateWeight: (name, weight) => set((state) => ({
    params: {
      ...state.params,
      selectedStrategies: state.params.selectedStrategies.map(s =>
        s.name === name ? { ...s, weight } : s
      )
    }
  })),

  // 自动均分权重
  autoBalanceWeights: () => set((state) => {
    const count = state.params.selectedStrategies.length;
    if (count === 0) return state;

    const weight = Math.floor(100 / count);
    const remainder = 100 - weight * count;

    return {
      params: {
        ...state.params,
        selectedStrategies: state.params.selectedStrategies.map((s, i) => ({
          ...s,
          weight: i === 0 ? weight + remainder : weight
        }))
      }
    };
  }),

  reset: () => set({ status: 'idle', progress: 0, currentSessionId: null, params: initialParams, activeTradeId: null }),
}));
