import type { MarkerData, OccupancyResponse } from "../types";
import type { PredictionMap } from "../hooks/usePredictions";
import {
  missingPredictionMarker,
  occupancyToMarker,
  predictionToMarker,
} from "./occupancy";

export function buildMarkerDataList(
  occ: OccupancyResponse[] | null,
  viewTime: Date | null,
  pred: PredictionMap,
  predictLoading: boolean,
  isDesktop: boolean = true,
): MarkerData[] {
  if (!occ?.length) return [];
  if (!viewTime) {
    return occ.map(occupancyToMarker);
  }
  if (predictLoading) {
    // On mobile: keep showing live data while predictions load (no jarring pending state)
    // On desktop: show pending state with visual feedback
    if (!isDesktop) {
      return occ.map(occupancyToMarker);
    }
    return occ.map((o) => ({
      ...occupancyToMarker(o),
      predictionPending: true,
    }));
  }
  return occ.map((o) => {
    const p = pred[o.car_park_id];
    if (!p || p === "missing") return missingPredictionMarker(o);
    return predictionToMarker(o, p);
  });
}
