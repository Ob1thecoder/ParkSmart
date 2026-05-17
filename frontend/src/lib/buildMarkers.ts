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
): MarkerData[] {
  if (!occ?.length) return [];
  if (!viewTime || predictLoading) {
    return occ.map(occupancyToMarker);
  }
  return occ.map((o) => {
    const p = pred[o.car_park_id];
    if (!p || p === "missing") return missingPredictionMarker(o);
    return predictionToMarker(o, p);
  });
}
