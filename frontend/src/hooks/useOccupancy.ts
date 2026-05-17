import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getOccupancy } from "../api";
import type { OccupancyResponse } from "../types";

const POLL_MS = 5 * 60 * 1000;

export function useOccupancy() {
  const [data, setData] = useState<OccupancyResponse[] | null>(null);
  const [stale, setStale] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const lastGoodRef = useRef<OccupancyResponse[] | null>(null);

  const fetchOccupancy = useCallback(async () => {
    try {
      const list = await getOccupancy();
      lastGoodRef.current = list;
      setData(list);
      setStale(false);
      setLoadError(null);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message || `HTTP ${e.status}`
          : e instanceof Error
            ? e.message
            : "Request failed";
      if (lastGoodRef.current) {
        setData(lastGoodRef.current);
        setStale(true);
      } else {
        setLoadError(msg);
      }
    }
  }, []);

  useEffect(() => {
    void fetchOccupancy();
    const id = window.setInterval(() => void fetchOccupancy(), POLL_MS);
    return () => window.clearInterval(id);
  }, [fetchOccupancy]);

  return { data, stale, loadError, retry: fetchOccupancy };
}
