import { useEffect, useRef, useState } from "react";
import { getPredict } from "../api";
import type { OccupancyResponse, PredictionResult } from "../types";

export type PredictionMap = Record<string, PredictionResult | "missing">;

function parkSignature(parks: OccupancyResponse[] | null): string {
  if (!parks?.length) return "";
  return parks
    .map((p) => `${p.car_park_id}\0${p.name}`)
    .sort()
    .join("|");
}

export function usePredictions(
  viewTime: Date | null,
  parks: OccupancyResponse[] | null,
): { byId: PredictionMap; loading: boolean } {
  const [byId, setById] = useState<PredictionMap>({});
  const [loading, setLoading] = useState(false);
  const parksRef = useRef(parks);
  parksRef.current = parks;
  const sig = parkSignature(parks);

  useEffect(() => {
    const list = parksRef.current;
    if (!viewTime || !list?.length) {
      setById({});
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    const iso = viewTime.toISOString();

    Promise.allSettled(list.map((p) => getPredict(p.name, iso))).then((results) => {
      if (cancelled) return;
      const next: PredictionMap = {};
      list.forEach((p, i) => {
        const r = results[i];
        if (r.status === "fulfilled") {
          next[p.car_park_id] = r.value;
        } else {
          next[p.car_park_id] = "missing";
        }
      });
      setById(next);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [viewTime, sig]);

  return { byId, loading };
}
