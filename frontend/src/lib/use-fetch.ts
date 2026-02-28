import { useCallback, useEffect, useRef, useState } from "react";

export interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  isValidating: boolean;
  refetch: () => void;
}

/**
 * SWR-style data fetching hook.
 * Serves cached data instantly while revalidating in the background.
 * No flash of loading state on revalidation.
 */
export function useFetch<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseFetchResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [tick, setTick] = useState(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (data !== null) {
      // Revalidation — keep showing stale data
      setIsValidating(true);
      setError(null);
      fetcher()
        .then((result) => {
          if (!cancelled && mountedRef.current) {
            setData(result);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled && mountedRef.current) {
            setError(err?.message || "Failed to load data");
          }
        })
        .finally(() => {
          if (!cancelled && mountedRef.current) setIsValidating(false);
        });
    } else {
      // First load
      setLoading(true);
      setError(null);
      fetcher()
        .then((result) => {
          if (!cancelled && mountedRef.current) setData(result);
        })
        .catch((err) => {
          if (!cancelled && mountedRef.current)
            setError(err?.message || "Failed to load data");
        })
        .finally(() => {
          if (!cancelled && mountedRef.current) setLoading(false);
        });
    }

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return { data, loading, error, isValidating, refetch };
}
