import type { OccupancyResponse, PredictionResult } from "../../types";
import type { PredictionMap } from "../../hooks/usePredictions";
import { occupancyColor, confidenceLevel } from "../../lib/occupancy";

type Props = {
  occupancy: OccupancyResponse[];
  loading?: boolean;
  predictions: PredictionMap;
  showLive: boolean;
  onToggle: (live: boolean) => void;
  onSelect?: (carParkId: string) => void;
  viewTime?: Date;
};

function formatViewTime(d: Date): string {
  return d.toLocaleString("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function OccupancyBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-black/[0.08]">
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, pct * 100))}%`, backgroundColor: color }}
      />
    </div>
  );
}

function CarParkCard({
  park,
  prediction,
  showLive,
  onClick,
}: {
  park: OccupancyResponse;
  prediction?: PredictionResult;
  showLive: boolean;
  onClick?: () => void;
}) {
  const pct = showLive ? park.occupancy_pct : (prediction?.predicted_occupancy_pct ?? park.occupancy_pct);
  const color = occupancyColor(pct);
  const isLive = park.source === "tfnsw";

  const confidence = prediction?.confidence;
  const level = confidence != null ? confidenceLevel(confidence) : null;

  return (
    <button
      onClick={onClick}
      className="w-full border-b border-black/5 px-4 py-3.5 text-left transition-colors hover:bg-park-mist/25"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate font-display text-[13px] font-semibold text-park-ink hover:text-park-fern">
          {park.name}
        </span>
        <span className="shrink-0 text-base font-bold tabular-nums" style={{ color }}>
          {Math.round(pct * 100)}%
        </span>
      </div>

      <OccupancyBar pct={pct} color={color} />

      <div className="mt-2 flex items-center justify-between gap-2">
        {showLive ? (
          <span className="text-[11px] text-park-slate">
            {park.occupied} occupied ·{" "}
            <span className="font-semibold text-park-fern">{park.available} free</span> /{" "}
            {park.capacity}
          </span>
        ) : level && confidence != null ? (
          <span className="text-[11px] text-park-slate">
            {level} confidence · {Math.round(confidence * 100)}%
          </span>
        ) : prediction?.model_version === "simulator-v1" ? (
          <span className="text-[11px] text-park-slate">Pattern-based estimate</span>
        ) : (
          <span className="text-[11px] text-park-slate">—</span>
        )}

        {showLive ? (
          isLive ? (
            <span className="rounded bg-park-fern/10 px-1.5 py-0.5 text-[9px] font-bold uppercase text-park-fern">
              ● Live
            </span>
          ) : (
            <span className="rounded bg-black/5 px-1.5 py-0.5 text-[9px] font-bold uppercase text-park-slate">
              ○ Est
            </span>
          )
        ) : (
          <span className="rounded bg-park-fern/10 px-1.5 py-0.5 text-[9px] font-bold uppercase text-park-fern">
            ◆ Predicted
          </span>
        )}
      </div>
    </button>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
      <svg
        className="h-8 w-8 animate-spin text-park-fern"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
        <path
          d="M12 2a10 10 0 019.95 9"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <p className="text-sm text-park-slate">Loading car parks…</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <svg
        className="h-10 w-10 text-park-slate/30"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <path d="M7 17m-2 0a2 2 0 104 0 2 2 0 10-4 0M17 17m-2 0a2 2 0 104 0 2 2 0 10-4 0" />
        <path d="M5 17H3v-6l2-5h9l4 5h1a2 2 0 012 2v4h-2m-4 0H9" />
      </svg>
      <p className="text-sm font-medium text-park-slate">No car parks found</p>
      <p className="text-xs text-park-slate/70">Check back shortly or refresh the page</p>
    </div>
  );
}

function getPrediction(predictions: PredictionMap, id: string): PredictionResult | undefined {
  const val = predictions[id];
  return val === "missing" ? undefined : val;
}

export function CarParksTab({ occupancy, loading, predictions, showLive, onToggle, onSelect, viewTime }: Props) {
  const sorted = [...occupancy].sort((a, b) => {
    const predA = getPrediction(predictions, a.car_park_id);
    const predB = getPrediction(predictions, b.car_park_id);
    const pctA = showLive ? a.occupancy_pct : (predA?.predicted_occupancy_pct ?? a.occupancy_pct);
    const pctB = showLive ? b.occupancy_pct : (predB?.predicted_occupancy_pct ?? b.occupancy_pct);
    return pctB - pctA;
  });

  if (loading) {
    return <LoadingState />;
  }

  if (occupancy.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-black/5 bg-white px-4 py-2.5 shadow-subtle">
        <div>
          <p className="text-xs font-semibold text-park-ink">
            {occupancy.length} car park{occupancy.length !== 1 ? "s" : ""} nearby
          </p>
          <p className="text-[10px] text-park-slate/55">● Updated just now</p>
        </div>
        <div className="flex overflow-hidden rounded-lg border border-black/10">
          <button
            onClick={() => onToggle(true)}
            className={`px-2.5 py-1 text-[11px] font-semibold transition-colors ${
              showLive ? "bg-park-ink text-white" : "bg-transparent text-park-slate"
            }`}
          >
            Live
          </button>
          <button
            onClick={() => onToggle(false)}
            className={`px-2.5 py-1 text-[11px] font-semibold transition-colors ${
              !showLive ? "bg-park-ink text-white" : "bg-transparent text-park-slate"
            }`}
          >
            {viewTime ? formatViewTime(viewTime) : "Predicted"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {sorted.map((park) => (
          <CarParkCard
            key={park.car_park_id}
            park={park}
            prediction={getPrediction(predictions, park.car_park_id)}
            showLive={showLive}
            onClick={() => onSelect?.(park.car_park_id)}
          />
        ))}
      </div>
    </div>
  );
}
