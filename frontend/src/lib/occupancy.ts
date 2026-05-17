import type { MarkerData, OccupancyResponse, PredictionResult } from "../types";

/** Occupancy colour thresholds — single source of truth (design spec §6). */
export function occupancyColor(pct: number): string {
  if (pct < 0.7) return "#1f6b4a";
  if (pct < 0.9) return "#c9780a";
  return "#b4232c";
}

export function occupancyToMarker(o: OccupancyResponse): MarkerData {
  return {
    id: o.car_park_id,
    name: o.name,
    lat: o.lat,
    lon: o.lon,
    pct: o.occupancy_pct,
    source: o.source,
    mode: "live",
  };
}

export function predictionToMarker(
  o: OccupancyResponse,
  p: PredictionResult,
): MarkerData {
  return {
    id: o.car_park_id,
    name: o.name,
    lat: o.lat,
    lon: o.lon,
    pct: p.predicted_occupancy_pct,
    source: o.source,
    mode: "predicted",
    confidence: p.confidence,
    modelVersion: p.model_version,
  };
}

export function missingPredictionMarker(o: OccupancyResponse): MarkerData {
  return {
    id: o.car_park_id,
    name: o.name,
    lat: o.lat,
    lon: o.lon,
    pct: o.occupancy_pct,
    source: o.source,
    mode: "predicted",
    predictionMissing: true,
  };
}

export function provenanceBadge(data: MarkerData): { label: string; className: string }[] {
  const badges: { label: string; className: string }[] = [];

  if (data.predictionMissing) {
    badges.push({
      label: "No prediction",
      className: "bg-zinc-200 text-zinc-800",
    });
    return badges;
  }

  if (data.mode === "live") {
    if (data.source === "tfnsw") {
      badges.push({ label: "Live", className: "bg-emerald-600 text-white" });
    } else {
      badges.push({ label: "Estimated", className: "bg-zinc-400 text-white" });
    }
    return badges;
  }

  if (data.modelVersion === "xgboost-v1" && data.confidence != null) {
    badges.push({
      label: `Predicted · ${Math.round(data.confidence * 100)}% confidence`,
      className: "bg-teal-700 text-white",
    });
  } else if (data.modelVersion === "simulator-v1") {
    badges.push({
      label: "Estimated · typical patterns",
      className: "bg-zinc-500 text-white",
    });
  } else if (data.modelVersion) {
    badges.push({ label: data.modelVersion, className: "bg-zinc-600 text-white" });
  }

  return badges;
}
