'use client';

import { createContext, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { DecisionData } from '@/lib/types/decision';

type Channel = 'trades' | 'positions' | 'trends' | 'indicators' | 'ticker' | 'decision' | 'backtest';

interface WebSocketData {
  trades?: any[];
  position?: any;
  trend?: any;
  indicators?: any[];
  ticker?: any;
  decision?: DecisionData;
  backtest?: any;
  updated_at?: string;
}

interface WebSocketContextType {
  data: WebSocketData;
  isConnected: boolean;
  error: string | null;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

const MAX_RETRIES = 5;
const INITIAL_RETRY_DELAY = 1000;
const DEFAULT_CHANNELS: Channel[] = ['trades', 'positions', 'trends', 'indicators', 'ticker', 'decision', 'backtest'];

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated, token, logout } = useAuth();
  const [data, setData] = useState<WebSocketData>({});
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const retryCountRef = useRef(0);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    if (!isAuthenticated || !token) {
      setData({});
      setError(null);
      return;
    }

    const connect = () => {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
      const ws = new WebSocket(`${wsUrl}/ws/stream?token=${token}`);

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        retryCountRef.current = 0;
        ws.send(JSON.stringify({ action: 'subscribe', channels: DEFAULT_CHANNELS }));
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setData(payload);
        } catch (error) {
          console.error('WebSocket: Failed to parse message', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = (event) => {
        setIsConnected(false);

        if (event.code === 4401 || event.code === 1008) {
          console.error('WebSocket: Authentication failed');
          logout();
          return;
        }

        if (isMountedRef.current && isAuthenticated && retryCountRef.current < MAX_RETRIES) {
          const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCountRef.current);
          retryCountRef.current += 1;
          console.log(`WebSocket: Reconnecting in ${delay}ms (attempt ${retryCountRef.current}/${MAX_RETRIES})`);
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        } else if (retryCountRef.current >= MAX_RETRIES) {
          setError('连接失败，请刷新页面重试');
          console.error('WebSocket: Max retries reached');
        }
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [isAuthenticated, token, logout]);

  return (
    <WebSocketContext.Provider value={{ data, isConnected, error }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider');
  }
  return context;
}
