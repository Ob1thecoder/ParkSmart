import type { ZoneResponse, ZoneSegment } from "../../types";
import { rulesForSegment, type ParsedRule } from "../../lib/formatStreetRules";

type Props = {
  zone: ZoneResponse | null;
  notFound: boolean;
  loadError: string | null;
  loading: boolean;
  streetQuery: string;
  onClose: () => void;
};

const RULE_STYLES: Record<ParsedRule["type"], { bg: string; text: string; border: string }> = {
  no_stopping: { bg: "#fef2f2", text: "#b91c1c", border: "#fecaca" },
  no_parking: { bg: "#fff7ed", text: "#c2410c", border: "#fed7aa" },
  timed: { bg: "#ecfdf5", text: "#047857", border: "#a7f3d0" },
  loading: { bg: "#faf5ff", text: "#7c3aed", border: "#ddd6fe" },
  permit_only: { bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe" },
  other: { bg: "#f9fafb", text: "#4b5563", border: "#e5e7eb" },
};

function RuleIcon({ type, color }: { type: ParsedRule["type"]; color: string }) {
  switch (type) {
    case "no_stopping":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
        </svg>
      );
    case "no_parking":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.5 9h3a2 2 0 110 4H9.5V9zM9.5 13v3" />
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
        </svg>
      );
    case "timed":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12,6 12,12 16,14" />
        </svg>
      );
    case "loading":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
          <rect x="1" y="3" width="15" height="13" rx="2" />
          <path d="M16 8h4l3 3v5h-7V8z" />
          <circle cx="5.5" cy="18.5" r="2.5" />
          <circle cx="18.5" cy="18.5" r="2.5" />
        </svg>
      );
    case "permit_only":
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M9 9h3a2 2 0 110 4H9V9zM9 13v3" />
        </svg>
      );
    default:
      return (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
      );
  }
}

function RuleCard({ rule }: { rule: ParsedRule }) {
  const style = RULE_STYLES[rule.type];
  
  return (
    <div
      className="rounded-lg p-3"
      style={{ backgroundColor: style.bg, border: `1px solid ${style.border}` }}
    >
      <div className="flex items-start gap-2.5">
        <div className="shrink-0 mt-0.5">
          <RuleIcon type={rule.type} color={style.text} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-[13px]" style={{ color: style.text }}>
            {rule.label}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-park-slate">
            <span className="flex items-center gap-1">
              <svg className="h-3 w-3 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12,6 12,12 16,14" />
              </svg>
              {rule.times}
            </span>
            <span className="flex items-center gap-1">
              <svg className="h-3 w-3 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              {rule.days}
            </span>
          </div>
          {rule.note ? (
            <p className="mt-1.5 text-[10px] italic text-park-slate/80">
              {rule.note}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SegmentRules({ segment }: { segment: ZoneSegment }) {
  const rules = rulesForSegment(segment);

  return (
    <div>
      {segment.side ? (
        <p className="mb-2 text-[11px] font-bold uppercase tracking-wide text-park-slate">
          {segment.side}
        </p>
      ) : null}
      <div className="space-y-2">
        {rules.map((rule, i) => (
          <RuleCard key={i} rule={rule} />
        ))}
      </div>
    </div>
  );
}

function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-black/5 text-park-slate transition-colors hover:bg-black/10"
      onClick={onClick}
      aria-label="Close street rules"
    >
      <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M2 2l8 8M10 2l-8 8" />
      </svg>
    </button>
  );
}

export function ZoneRulesCard({
  zone,
  notFound,
  loadError,
  loading,
  streetQuery,
  onClose,
}: Props) {
  const showPanel = loading || loadError || (notFound && !!streetQuery) || !!zone;
  if (!showPanel) return null;

  if (loading) {
    return (
      <div className="mt-2 overflow-hidden rounded-xl border border-black/10 bg-white/95 shadow-md">
        <div className="flex items-center justify-between border-b border-black/5 bg-park-mist/60 px-3 py-2">
          <span className="text-xs font-bold uppercase tracking-wide text-park-slate">Street Parking Rules</span>
          <CloseButton onClick={onClose} />
        </div>
        <div className="p-4 text-sm text-park-slate">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-park-fern border-t-transparent align-[-2px]" />{" "}
          Loading rules…
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="mt-2 overflow-hidden rounded-xl border border-black/10 bg-white/95 shadow-md">
        <div className="flex items-center justify-between border-b border-black/5 bg-red-50/80 px-3 py-2">
          <span className="text-xs font-bold uppercase tracking-wide text-red-900">Street Parking Rules</span>
          <CloseButton onClick={onClose} />
        </div>
        <div className="p-4 text-sm">
          <p className="font-medium text-park-brick">{loadError}</p>
        </div>
      </div>
    );
  }

  if (notFound && streetQuery) {
    return (
      <div className="mt-2 overflow-hidden rounded-xl border border-black/10 bg-white/95 shadow-md">
        <div className="flex items-center justify-between border-b border-black/5 bg-park-mist/60 px-3 py-2">
          <span className="text-xs font-bold uppercase tracking-wide text-park-slate">Street Parking Rules</span>
          <CloseButton onClick={onClose} />
        </div>
        <div className="p-4 text-sm">
          <p className="font-medium text-park-ink">
            No parking rules found for <em>{streetQuery}</em>
          </p>
        </div>
      </div>
    );
  }

  if (!zone) return null;

  return (
    <div className="mt-2 max-h-[min(70vh,28rem)] overflow-hidden rounded-xl border border-black/10 bg-white/95 shadow-md">
      <div className="flex items-center justify-between border-b border-black/5 bg-park-mist/60 px-3 py-2.5">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wide text-park-slate">Street Parking Rules</div>
          <div className="font-display text-sm font-semibold text-park-ink">{zone.street}</div>
        </div>
        <CloseButton onClick={onClose} />
      </div>
      <div className="max-h-[min(55vh,22rem)] space-y-4 overflow-y-auto p-3">
        {zone.segments.map((seg, i) => (
          <SegmentRules key={i} segment={seg} />
        ))}
        <p className="border-t border-black/5 pt-3 text-[10px] text-park-slate">
          Data source: Willoughby Council • Always check signs on arrival
        </p>
      </div>
    </div>
  );
}
