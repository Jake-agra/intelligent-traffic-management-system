import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import type { RealtimeEventEnvelope } from "../api/types";

type ConnectionStatus = "connecting" | "connected" | "disconnected" | "offline";

interface RealtimeContextValue {
  status: ConnectionStatus;
  lastEvent: RealtimeEventEnvelope | null;
  events: RealtimeEventEnvelope[];
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);
const DEFAULT_WS_BASE_URL = "ws://127.0.0.1:8000";

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [events, setEvents] = useState<RealtimeEventEnvelope[]>([]);
  const seenEventIds = useRef(new Set<string>());
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const heartbeatTimer = useRef<number | null>(null);
  const attemptRef = useRef(0);

  const clearTimers = useCallback(() => {
    if (reconnectTimer.current !== null) {
      window.clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (heartbeatTimer.current !== null) {
      window.clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
  }, []);

  useEffect(() => {
    let disposed = false;

    function connect() {
      if (disposed) {
        return;
      }
      setStatus(navigator.onLine ? "connecting" : "offline");
      const socket = new WebSocket(`${wsBaseUrl()}/api/v1/ws`);
      socketRef.current = socket;

      socket.onopen = () => {
        attemptRef.current = 0;
        setStatus("connected");
        heartbeatTimer.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
          }
        }, 30000);
      };

      socket.onmessage = (message) => {
        const parsed = parseRealtimeMessage(message.data);
        if (!parsed || "type" in parsed) {
          return;
        }
        if (seenEventIds.current.has(parsed.event_id)) {
          return;
        }
        seenEventIds.current.add(parsed.event_id);
        setEvents((current) => [parsed, ...current].slice(0, 50));
      };

      socket.onclose = () => {
        if (heartbeatTimer.current !== null) {
          window.clearInterval(heartbeatTimer.current);
          heartbeatTimer.current = null;
        }
        if (disposed) {
          return;
        }
        setStatus(navigator.onLine ? "disconnected" : "offline");
        const delay = Math.min(1000 * 2 ** attemptRef.current, 10000);
        attemptRef.current += 1;
        reconnectTimer.current = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();
    return () => {
      disposed = true;
      clearTimers();
      socketRef.current?.close();
    };
  }, [clearTimers]);

  const value = useMemo(
    () => ({ status, lastEvent: events[0] ?? null, events }),
    [events, status]
  );

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime(): RealtimeContextValue {
  const value = useContext(RealtimeContext);
  if (value === null) {
    throw new Error("useRealtime must be used within RealtimeProvider.");
  }
  return value;
}

function wsBaseUrl(): string {
  return import.meta.env.VITE_WS_BASE_URL ?? DEFAULT_WS_BASE_URL;
}

function parseRealtimeMessage(value: unknown): RealtimeEventEnvelope | { type: string } | null {
  if (typeof value !== "string") {
    return null;
  }
  try {
    return JSON.parse(value) as RealtimeEventEnvelope | { type: string };
  } catch {
    return null;
  }
}
