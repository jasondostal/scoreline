import { useEffect, useRef, useState, useCallback } from "react";

interface WebSocketEvent {
  type: string;
  [key: string]: unknown;
}

interface UseWebSocketOptions {
  onMessage: (event: WebSocketEvent) => void;
}

export function useWebSocket({ onMessage }: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoff = useRef(1000);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => {
      setConnected(true);
      backoff.current = 1000; // Reset backoff on successful connect
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onMessageRef.current(data);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      // Reconnect with exponential backoff
      reconnectTimer.current = setTimeout(() => {
        backoff.current = Math.min(backoff.current * 2, 30000);
        connect();
      }, backoff.current);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { connected };
}
