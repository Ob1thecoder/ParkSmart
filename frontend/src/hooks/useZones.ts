import { useCallback, useState } from "react";
import { ApiError, getZones } from "../api";
import type { ZoneResponse } from "../types";

export function useZones() {
  const [zone, setZone] = useState<ZoneResponse | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [streetQuery, setStreetQuery] = useState("");

  const load = useCallback(async (street: string) => {
    const q = street.trim();
    setStreetQuery(q);
    if (!q) {
      setZone(null);
      setNotFound(false);
      setLoadError(null);
      return;
    }
    setLoading(true);
    setNotFound(false);
    setLoadError(null);
    try {
      const z = await getZones(q);
      setZone(z);
    } catch (e) {
      setZone(null);
      if (e instanceof ApiError && e.status === 404) {
        setNotFound(true);
      } else {
        setLoadError("Could not load parking rules — please try again.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  return { zone, notFound, loadError, loading, streetQuery, load };
}
