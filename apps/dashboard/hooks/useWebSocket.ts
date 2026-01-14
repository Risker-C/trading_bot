import { useEffect, useRef, useState } from 'react';

type Channel = 'trades' | 'positions' | 'trends' | 'indicators';

interface WebSocketData {
  trades?: any[];
  position?: any;
  trend?: any;
  indicators?: any[];
  updated_at?: string;
}

const MAX_RETRIES = 5;
const INITIAL_RETRY_DELAY = 1000; // 1秒

export function useWebSocket(channels: Channel[] = ['trades', 'positions', 'trends', 'indicators']) {
  const [data, setData] = useState<WebSocketData>({});
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const retryCountRef = useRef(0);

  useEffect(() => {
    const connect = () => {
      // 修复问题1: 使用 access_token 与 API 客户端保持一致
      const token = localStorage.getItem('access_token');

      // 修复问题2: token 缺失时停止连接
      if (!token) {
        console.error('WebSocket: No access token found, skipping connection');
        return;
      }

      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
      const ws = new WebSocket(`${wsUrl}/ws/stream?token=${token}`);

      ws.onopen = () => {
        setIsConnected(true);
        retryCountRef.current = 0; // 重置重试计数
        ws.send(JSON.stringify({ action: 'subscribe', channels }));
      };

      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        setData(payload);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        setIsConnected(false);

        // 修复问题3: 指数退避重试策略
        if (retryCountRef.current < MAX_RETRIES) {
          const delay = INITIAL_RETRY_DELAY * Math.pow(2, retryCountRef.current);
          retryCountRef.current += 1;

          console.log(`WebSocket: Reconnecting in ${delay}ms (attempt ${retryCountRef.current}/${MAX_RETRIES})`);
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        } else {
          console.error('WebSocket: Max retries reached, giving up');
        }
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, [channels.join(',')]);

  return { data, isConnected };
}
