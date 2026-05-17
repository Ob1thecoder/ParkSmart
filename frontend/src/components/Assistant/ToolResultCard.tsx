import { occupancyColor, confidenceLevel, confidenceColor } from "../../lib/occupancy";

type ToolName = "get_live_occupancy" | "predict_availability" | "get_zone_restrictions";

const TOOL_CONFIG: Record<
  ToolName,
  { label: string; color: string; bgTint: string; borderLight: string }
> = {
  get_live_occupancy: {
    label: "Live check",
    color: "#16a34a",
    bgTint: "rgba(22, 163, 74, 0.03)",
    borderLight: "rgba(22, 163, 74, 0.12)",
  },
  predict_availability: {
    label: "Prediction",
    color: "#c9780a",
    bgTint: "rgba(201, 120, 10, 0.03)",
    borderLight: "rgba(201, 120, 10, 0.12)",
  },
  get_zone_restrictions: {
    label: "Street rules",
    color: "#1d4ed8",
    bgTint: "rgba(29, 78, 216, 0.03)",
    borderLight: "rgba(29, 78, 216, 0.12)",
  },
};

function isToolName(s: string): s is ToolName {
  return s in TOOL_CONFIG;
}

type Props = {
  tool: string;
  input: Record<string, unknown>;
  result?: Record<string, unknown>;
  isRunning: boolean;
};

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-AU", {
      hour: "numeric",
      minute: "2-digit",
      timeZone: "Australia/Sydney",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-AU", {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
      timeZone: "Australia/Sydney",
    });
  } catch {
    return iso;
  }
}

function OccupancyBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/[0.08]">
      <div
        className="h-full rounded-full transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, pct * 100))}%`, backgroundColor: color }}
      />
    </div>
  );
}

function OccupancyResult({ result }: { result: Record<string, unknown> }) {
  const name = String(result.name ?? "Car Park");
  const pct = Number(result.occupancy_pct ?? 0);
  const occupied = result.occupied as number | undefined;
  const available = result.available as number | undefined;
  const capacity = result.capacity as number | undefined;
  const source = result.source as string | undefined;
  const asOf = result.as_of as string | undefined;
  const color = occupancyColor(pct);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-xs font-semibold text-park-ink">{name}</span>
        <span className="shrink-0 text-[15px] font-bold tabular-nums" style={{ color }}>
          {Math.round(pct * 100)}%
        </span>
      </div>
      <OccupancyBar pct={pct} color={color} />
      {occupied != null && available != null && capacity != null ? (
        <p className="mt-1.5 text-[11px] text-park-slate">
          {occupied} occupied · <span className="font-semibold text-park-fern">{available} free</span>{" "}
          / {capacity}
        </p>
      ) : null}
      {source || asOf ? (
        <p className="mt-1 text-[10px] text-park-slate/50">
          {source === "tfnsw" ? "● TfNSW live sensor" : "○ Est"}{" "}
          {asOf ? `· ${formatTime(asOf)}` : ""}
        </p>
      ) : null}
    </div>
  );
}

function PredictionResult({ result }: { result: Record<string, unknown> }) {
  const name = String(result.name ?? "Car Park");
  const pct = Number(result.predicted_occupancy_pct ?? 0);
  const confidence = result.confidence as number | undefined;
  const targetDatetime = result.target_datetime as string | undefined;
  const modelVersion = result.model_version as string | undefined;
  const color = occupancyColor(pct);

  const level = confidence != null ? confidenceLevel(confidence) : null;
  const levelColor = level ? confidenceColor(level) : "#5c6f66";

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="truncate text-xs font-semibold text-park-ink">{name}</span>
        <span className="shrink-0 text-[15px] font-bold tabular-nums" style={{ color }}>
          {Math.round(pct * 100)}%
        </span>
      </div>
      <OccupancyBar pct={pct} color={color} />
      {targetDatetime ? (
        <p className="mt-1.5 text-[11px] text-park-slate">{formatDateTime(targetDatetime)}</p>
      ) : null}
      {level && confidence != null ? (
        <p className="mt-1 text-[9px] font-bold" style={{ color: levelColor }}>
          {level} · {Math.round(confidence * 100)}%
        </p>
      ) : modelVersion === "simulator-v1" ? (
        <p className="mt-1 text-[9px] text-park-slate">Pattern-based estimate</p>
      ) : null}
    </div>
  );
}

function ZoneResult({ result }: { result: Record<string, unknown> }) {
  const street = String(result.street ?? "");
  const segments = (result.segments ?? []) as Array<{ side?: string; rules_plain_english?: string }>;

  return (
    <div>
      <p className="text-xs font-semibold text-park-ink">{street}</p>
      {segments.slice(0, 2).map((seg, i) => (
        <p key={i} className="mt-1 text-[11px] text-park-slate">
          {seg.side ? <span className="font-medium uppercase">{seg.side}: </span> : null}
          {seg.rules_plain_english?.slice(0, 80)}
          {(seg.rules_plain_english?.length ?? 0) > 80 ? "…" : ""}
        </p>
      ))}
      {segments.length > 2 ? (
        <p className="mt-1 text-[10px] text-park-slate/60">+{segments.length - 2} more sides</p>
      ) : null}
    </div>
  );
}

export function ToolResultCard({ tool, input, result, isRunning }: Props) {
  const config = isToolName(tool)
    ? TOOL_CONFIG[tool]
    : { label: tool, color: "#5c6f66", bgTint: "rgba(92, 111, 102, 0.03)", borderLight: "rgba(0,0,0,0.08)" };

  const hasError = result && "error" in result;

  return (
    <div
      className="mt-2 animate-slide-in overflow-hidden rounded-xl"
      style={{
        border: `1px solid ${config.borderLight}`,
        background: config.bgTint,
      }}
    >
      <div
        className="flex items-center gap-2 border-b px-3 py-2"
        style={{
          borderLeftWidth: 3,
          borderLeftColor: config.color,
          borderBottomColor: config.borderLight,
        }}
      >
        {isRunning ? (
          <svg
            className="h-[11px] w-[11px] animate-spin"
            style={{ color: config.color }}
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
        ) : (
          <span
            className="h-[11px] w-[11px] rounded-full"
            style={{ backgroundColor: config.color }}
          />
        )}
        <span className="text-[11px] font-semibold" style={{ color: config.color }}>
          {config.label}
        </span>
        <span className="ml-auto text-[10px] text-park-slate/35">
          {isRunning ? "running…" : "done"}
        </span>
      </div>

      <div
        className="px-3 py-2.5"
        style={{ borderLeftWidth: 3, borderLeftColor: config.color }}
      >
        {isRunning ? (
          <div className="flex items-center gap-2 text-[11px] text-park-slate">
            <svg
              className="h-3 w-3 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              style={{ color: config.color }}
            >
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
              <path
                d="M12 2a10 10 0 019.95 9"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
            Fetching data…
          </div>
        ) : hasError ? (
          <p className="text-[11px] text-park-brick">
            {String((result as Record<string, unknown>).detail ?? (result as Record<string, unknown>).error ?? "Error")}
          </p>
        ) : result ? (
          tool === "get_live_occupancy" ? (
            <OccupancyResult result={result} />
          ) : tool === "predict_availability" ? (
            <PredictionResult result={result} />
          ) : tool === "get_zone_restrictions" ? (
            <ZoneResult result={result} />
          ) : (
            <pre className="max-h-20 overflow-auto text-[10px] text-park-slate">
              {JSON.stringify(result, null, 2)}
            </pre>
          )
        ) : null}
      </div>
    </div>
  );
}
