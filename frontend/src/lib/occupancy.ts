import type { MarkerData, OccupancyResponse, PredictionResult } from "../types";

/** Occupancy colour thresholds — single source of truth (design spec §6). */
export function occupancyColor(pct: number): string {
  if (pct < 0.7) return "#1f6b4a";
  if (pct < 0.9) return "#c9780a";
  return "#b4232c";
}

export function occupancyToMarker(o: OccupancyResponse): MarkerData {
  // Clamp values to handle bad sensor data
  const pct = Math.max(0, Math.min(1, o.occupancy_pct));
  const available = Math.max(0, Math.min(o.available, o.capacity));
  const occupied = Math.max(0, o.capacity - available);

  return {
    id: o.car_park_id,
    name: o.name,
    lat: o.lat,
    lon: o.lon,
    pct,
    source: o.source,
    mode: "live",
    capacity: o.capacity,
    occupied,
    available,
  };
}

export function predictionToMarker(
  o: OccupancyResponse,
  p: PredictionResult,
): MarkerData {
  const cap = o.capacity;
  const occ = Math.round(p.predicted_occupancy_pct * cap);
  const avail = Math.max(0, cap - occ);
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
    capacity: cap,
    occupied: cap > 0 ? occ : undefined,
    available: cap > 0 ? avail : undefined,
    targetDatetime: p.target_datetime,
  };
}

export function confidenceLevel(confidence: number): "High" | "Medium" | "Low" {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}

export function confidenceColor(level: "High" | "Medium" | "Low"): string {
  if (level === "High") return "#16a34a";
  if (level === "Medium") return "#c9780a";
  return "#b4232c";
}

export function missingPredictionMarker(o: OccupancyResponse): MarkerData {
  // Clamp values to handle bad sensor data
  const pct = Math.max(0, Math.min(1, o.occupancy_pct));
  const available = Math.max(0, Math.min(o.available, o.capacity));
  const occupied = Math.max(0, o.capacity - available);

  return {
    id: o.car_park_id,
    name: o.name,
    lat: o.lat,
    lon: o.lon,
    pct,
    source: o.source,
    mode: "predicted",
    predictionMissing: true,
    capacity: o.capacity,
    occupied,
    available,
  };
}

export function provenanceBadge(data: MarkerData): { label: string; className: string }[] {
  const badges: { label: string; className: string }[] = [];

  if (data.predictionPending) {
    badges.push({
      label: "Calculating prediction…",
      className: "bg-violet-100 text-violet-900 ring-1 ring-violet-300",
    });
    return badges;
  }

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
