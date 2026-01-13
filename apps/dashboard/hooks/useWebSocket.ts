import { useEffect, useRef, useState } from 'react';

type Channel = 'trades' | 'positions' | 'trends' | 'indicators';

interface WebSocketData {
  trades?: any[];
  position?: any;
  trend?: any;
  indicators?: any[];
  updated_at?: string;
}

export function useWebSocket(channels: Channel[] = ['trades', 'positions', 'trends', 'indicators']) {
  const [data, setData] = useState<WebSocketData>({});
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const connect = () => {
      const token = localStorage.getItem('token');
      const ws = new WebSocket(`ws://localhost:8000/ws/stream?token=${token}`);

      ws.onopen = () => {
        setIsConnected(true);
        ws.send(JSON.stringify({ action: 'subscribe', channels }));
      };

      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        setData(payload);
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
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
