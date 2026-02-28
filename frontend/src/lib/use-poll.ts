import { useCallback, useEffect, useRef, useState } from "react";

export interface UsePollResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Visibility-aware polling hook.
 * Pauses when tab is hidden, resumes immediately on focus.
 * Optional shouldPause callback for interaction-aware pausing.
 */
export function usePoll<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  options?: { shouldPause?: () => boolean },
): UsePollResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  const shouldPauseRef = useRef(options?.shouldPause);

  fetcherRef.current = fetcher;
  shouldPauseRef.current = options?.shouldPause;

  const doFetch = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      if (mountedRef.current) {
        setData(result);
        setError(null);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : "Failed to load data");
        setLoading(false);
      }
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    mountedRef.current = true;
    doFetch();
    return () => {
      mountedRef.current = false;
    };
  }, [doFetch]);

  // Polling with visibility awareness
  useEffect(() => {
    const interval = setInterval(() => {
      if (document.hidden) return;
      if (shouldPauseRef.current?.()) return;
      doFetch();
    }, intervalMs);

    const handleVisibility = () => {
      if (!document.hidden) doFetch();
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [intervalMs, doFetch]);

  return { data, loading, error, refetch: doFetch };
}
