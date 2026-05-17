import type { MarkerData } from "../../types";
import { occupancyColor } from "../../lib/occupancy";
import L from "leaflet";

export function createParkDivIcon(data: MarkerData): L.DivIcon {
  const fill = data.predictionMissing ? "#94a3b8" : occupancyColor(data.pct);
  const outlined = data.source === "simulated";
  const label = data.predictionMissing ? "—" : `${Math.round(data.pct * 100)}`;
  const bg = outlined && !data.predictionMissing ? "#fff" : fill;
  const border = outlined
    ? `3px solid ${fill}`
    : "2px solid rgba(12,26,20,0.2)";
  const fg = outlined && !data.predictionMissing ? fill : "#fff";

  return L.divIcon({
    className: "park-marker-wrap",
    html: `<div class="park-pin" style="
      width:26px;height:26px;border-radius:999px;
      background:${bg};border:${border};
      box-shadow:0 2px 10px rgba(12,26,20,0.28);
      display:flex;align-items:center;justify-content:center;
      font:700 10px/1 DM Sans,system-ui,sans-serif;color:${fg};
    ">${label}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}
