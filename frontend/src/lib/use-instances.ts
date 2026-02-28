import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { api } from "./api";
import { usePoll } from "./use-poll";
import { useWebSocket } from "./use-websocket";
import { POLL_INTERVAL_MS } from "./constants";
import type { Instance } from "./types";

export function useInstances() {
  const [wsData, setWsData] = useState<Instance[] | null>(null);
  const wsConnected = useRef(false);

  const { connected } = useWebSocket({
    onMessage: (event) => {
      if (event.type === "instances_update") {
        setWsData(event.data as Instance[]);
      } else if (event.type === "game_started") {
        toast.info(`${event.away_team} @ ${event.home_team} started`, {
          duration: 8000,
        });
      } else if (event.type === "game_ended") {
        toast(`FINAL: ${event.away_team} ${event.away_score}, ${event.home_team} ${event.home_score}`, {
          duration: 10000,
        });
      }
    },
  });
  wsConnected.current = connected;

  // REST polling as fallback when WebSocket is disconnected
  const poll = usePoll(() => api.instances(), POLL_INTERVAL_MS, {
    shouldPause: () => wsConnected.current,
  });

  const refetch = useCallback(async () => {
    // Force a REST fetch for immediate feedback after mutations
    // Must update wsData directly since polling is paused when WS is connected
    try {
      const data = await api.instances();
      setWsData(data);
    } catch {
      poll.refetch();
    }
  }, [poll]);

  // Prefer WebSocket data when available, fall back to poll data
  const data = wsData ?? poll.data;
  const loading = data === null && poll.loading;
  const error = !connected && poll.error ? poll.error : null;

  return { data, loading, error, refetch, connected };
}
