import type { MarkerData } from "../../types";
import { occupancyColor, confidenceLevel, confidenceColor } from "../../lib/occupancy";

const SYDNEY_TZ = "Australia/Sydney";

function formatDate(isoOrDate: string | Date): string {
  const d = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-AU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: SYDNEY_TZ,
  }).format(d);
}

function formatTime(isoOrDate: string | Date): string {
  const d = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-AU", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: SYDNEY_TZ,
    timeZoneName: "short",
  }).format(d);
}

type StatusConfig = {
  bg: string;
  dotColor: string;
  textColor: string;
  label: string;
  dotSymbol?: string;
  pulse?: boolean;
};

type Props = {
  data: MarkerData;
  asOf?: string;
  viewTime: Date | null;
  compact?: boolean;
  onClose?: () => void;
};

function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-black/5 text-current transition-colors hover:bg-black/10"
      onClick={onClick}
      aria-label="Close"
    >
      <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M2 2l8 8M10 2l-8 8" />
      </svg>
    </button>
  );
}

function InfoRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2.5 border-t border-black/5 px-3 py-2.5 first:border-t-0">
      <span className="mt-0.5 shrink-0 text-park-slate/50">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] font-bold uppercase tracking-wide text-park-slate">{label}</div>
        <div className="mt-0.5 text-[13px] font-medium text-park-ink">{value}</div>
      </div>
    </div>
  );
}

function CalendarIcon() {
  return (
    <svg className="h-[13px] w-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg className="h-[13px] w-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12,6 12,12 16,14" />
    </svg>
  );
}

function CarIcon() {
  return (
    <svg className="h-[13px] w-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M7 17m-2 0a2 2 0 104 0 2 2 0 10-4 0M17 17m-2 0a2 2 0 104 0 2 2 0 10-4 0" />
      <path d="M5 17H3v-6l2-5h9l4 5h1a2 2 0 012 2v4h-2m-4 0H9" />
    </svg>
  );
}

export function CarParkDetail({ data, asOf, viewTime, compact, onClose }: Props) {
  const pct = data.predictionMissing ? 0 : data.pct;
  const pctColor = data.predictionMissing ? "#5c6f66" : occupancyColor(data.pct);
  const cap = data.capacity ?? 0;
  const occ = data.occupied;
  const avail = data.available;
  const showCounts = cap > 0 && occ != null && avail != null && !data.predictionPending && data.mode === "live";

  let status: StatusConfig;
  if (data.predictionPending) {
    status = {
      bg: "#f9fafb",
      dotColor: "#9ca3af",
      textColor: "#6b7280",
      label: "CALCULATING…",
    };
  } else if (data.mode === "predicted") {
    status = {
      bg: "#f0fdf4",
      dotColor: "#1f6b4a",
      textColor: "#1f6b4a",
      label: "PREDICTION",
      dotSymbol: "◆",
    };
  } else if (data.source === "tfnsw") {
    status = {
      bg: "#ecfdf5",
      dotColor: "#16a34a",
      textColor: "#15803d",
      label: "LIVE DATA",
      pulse: true,
    };
  } else {
    status = {
      bg: "#f9fafb",
      dotColor: "#9ca3af",
      textColor: "#6b7280",
      label: "ESTIMATED",
    };
  }

  const dateTime =
    data.predictionPending && viewTime
      ? viewTime
      : data.mode === "predicted" && viewTime
        ? viewTime
        : asOf
          ? new Date(asOf)
          : null;

  const dateLabel = data.mode === "predicted" ? "Prediction for" : "Captured on";

  const confidence = data.mode === "predicted" && data.confidence != null ? data.confidence : null;
  const confLevel = confidence != null ? confidenceLevel(confidence) : null;
  const confColor = confLevel ? confidenceColor(confLevel) : "#5c6f66";

  return (
    <div
      className={
        compact
          ? "min-w-[260px] overflow-hidden rounded-xl border border-black/[0.07] bg-white text-park-ink shadow-md"
          : "overflow-hidden rounded-xl border border-black/[0.07] bg-white shadow-lg"
      }
    >
      <div
        className="flex items-center justify-between gap-2 px-3 py-2"
        style={{ backgroundColor: status.bg }}
      >
        <div className="flex items-center gap-2">
          {status.dotSymbol ? (
            <span className="text-sm" style={{ color: status.dotColor }}>
              {status.dotSymbol}
            </span>
          ) : (
            <span className="relative flex h-2.5 w-2.5 items-center justify-center">
              <span
                className="absolute inline-flex h-full w-full rounded-full"
                style={{ backgroundColor: status.dotColor }}
              />
              {status.pulse ? (
                <span
                  className="absolute inline-flex h-full w-full rounded-full animate-ps-live-pulse"
                  style={{ backgroundColor: status.dotColor }}
                />
              ) : null}
            </span>
          )}
          <span className="text-xs font-bold tracking-wide" style={{ color: status.textColor }}>
            {status.label}
          </span>
        </div>
        {!compact && onClose ? <CloseButton onClick={onClose} /> : null}
      </div>

      <div className={compact ? "p-3" : "p-4"}>
        <h3 className={`font-display font-semibold text-park-ink ${compact ? "text-base" : "text-lg"}`}>
          {data.name}
        </h3>

        <div className="mt-4 text-center">
          <span className="text-4xl font-bold tabular-nums" style={{ color: pctColor }}>
            {data.predictionPending ? "…" : `${Math.round(data.pct * 100)}%`}
          </span>
          <span className="ml-1.5 text-sm text-park-slate">occupied</span>
        </div>

        {!data.predictionPending && !data.predictionMissing ? (
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/[0.08]">
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${Math.min(100, Math.max(0, pct * 100))}%`,
                backgroundColor: pctColor,
              }}
            />
          </div>
        ) : null}
      </div>

      <div className="mx-4 mb-4 overflow-hidden rounded-xl border border-black/[0.07] bg-[#f9fcf9]">
        {dateTime ? (
          <>
            <InfoRow icon={<CalendarIcon />} label={dateLabel} value={formatDate(dateTime)} />
            <InfoRow icon={<ClockIcon />} label="Time" value={formatTime(dateTime)} />
          </>
        ) : null}

        {showCounts ? (
          <InfoRow
            icon={<CarIcon />}
            label="Spaces"
            value={
              <>
                {occ} occupied · <span className="font-semibold text-park-fern">{avail} free</span>
              </>
            }
          />
        ) : null}

        {data.mode === "predicted" && !data.predictionMissing && !data.predictionPending ? (
          <InfoRow
            icon={
              <svg className="h-[13px] w-[13px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 20V10M6 20V4M18 20V16" />
              </svg>
            }
            label="Confidence"
            value={
              confLevel && confidence != null ? (
                <span className="flex items-center gap-2">
                  <span
                    className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase"
                    style={{
                      backgroundColor: `${confColor}15`,
                      color: confColor,
                    }}
                  >
                    {confLevel}
                  </span>
                  <span className="tabular-nums">{Math.round(confidence * 100)}%</span>
                </span>
              ) : data.modelVersion === "simulator-v1" ? (
                "Pattern-based estimate"
              ) : (
                "—"
              )
            }
          />
        ) : null}

        <div className="border-t border-black/5 bg-park-mist/20 px-3 py-2">
          <p className="text-[10px] text-park-slate">
            {data.mode === "predicted" ? (
              data.modelVersion === "xgboost-v1" ? (
                "◆ XGBoost model · TfNSW-trained"
              ) : data.modelVersion === "simulator-v1" ? (
                "○ Simulator · typical patterns"
              ) : (
                `○ ${data.modelVersion ?? "Model"}`
              )
            ) : data.source === "tfnsw" ? (
              "● TfNSW real-time sensor"
            ) : (
              "○ Estimated · not sensor data"
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
