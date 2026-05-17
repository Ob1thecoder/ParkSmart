import type { MarkerData } from "../../types";
import { occupancyColor, provenanceBadge } from "../../lib/occupancy";

type Props = {
  data: MarkerData;
  asOf?: string;
  compact?: boolean;
  onClose?: () => void;
};

export function CarParkDetail({ data, asOf, compact, onClose }: Props) {
  const badges = provenanceBadge(data);
  const pctLabel = data.predictionMissing
    ? "No prediction"
    : `${Math.round(data.pct * 100)}% full`;
  const pctColor = data.predictionMissing ? "#5c6f66" : occupancyColor(data.pct);

  return (
    <div className={compact ? "text-park-ink" : "rounded-2xl bg-white p-4 shadow-lg"}>
      {!compact && onClose ? (
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            className="text-sm text-park-slate underline"
            onClick={onClose}
          >
            Close
          </button>
        </div>
      ) : null}
      <h3
        className={`font-display font-semibold text-park-ink ${compact ? "text-base" : "text-lg"}`}
      >
        {data.name}
      </h3>
      <p
        className="mt-1 text-2xl font-semibold tracking-tight"
        style={{ color: pctColor }}
      >
        {pctLabel}
      </p>
      {data.mode === "live" && asOf ? (
        <p className="mt-1 text-xs text-park-slate">As of {new Date(asOf).toLocaleString()}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {badges.map((b) => (
          <span
            key={b.label}
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide ${b.className}`}
          >
            {b.label}
          </span>
        ))}
      </div>
      {data.mode === "live" && data.source === "tfnsw" ? (
        <p className="mt-2 text-xs text-emerald-800">Live TfNSW sensor data</p>
      ) : null}
      {data.mode === "live" && data.source === "simulated" ? (
        <p className="mt-2 text-xs text-park-slate">
          Pattern-based estimate for this CBD facility (not a live sensor).
        </p>
      ) : null}
    </div>
  );
}
