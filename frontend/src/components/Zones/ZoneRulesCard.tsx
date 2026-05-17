import type { ZoneResponse } from "../../types";

type Props = {
  zone: ZoneResponse | null;
  notFound: boolean;
  loadError: string | null;
  loading: boolean;
  streetQuery: string;
};

export function ZoneRulesCard({ zone, notFound, loadError, loading, streetQuery }: Props) {
  if (loading) {
    return (
      <div className="mt-2 rounded-xl border border-black/5 bg-white/95 p-4 text-sm text-park-slate shadow-md">
        Loading rules…
      </div>
    );
  }
  if (loadError) {
    return (
      <div className="mt-2 rounded-xl border border-black/5 bg-white/95 p-4 text-sm shadow-md">
        <p className="font-medium text-park-brick">{loadError}</p>
      </div>
    );
  }
  if (notFound && streetQuery) {
    return (
      <div className="mt-2 rounded-xl border border-black/5 bg-white/95 p-4 text-sm shadow-md">
        <p className="font-medium text-park-ink">
          No parking rules found for <em>{streetQuery}</em>
        </p>
      </div>
    );
  }
  if (!zone) return null;

  return (
    <div className="mt-2 max-h-64 overflow-y-auto rounded-xl border border-black/5 bg-white/95 p-4 text-sm shadow-md">
      <h4 className="font-display text-base font-semibold text-park-ink">{zone.street}</h4>
      <ul className="mt-3 space-y-3">
        {zone.segments.map((seg, i) => (
          <li
            key={i}
            className="rounded-lg border border-black/5 bg-park-mist/50 p-3"
          >
            {seg.side ? (
              <p className="text-[10px] font-bold uppercase tracking-wide text-park-slate">
                Side: {seg.side}
              </p>
            ) : null}
            <p className="mt-1 text-park-ink">{seg.rules_plain_english}</p>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-black/5 pt-2 text-[11px] font-semibold text-park-slate">
        Source: Willoughby Council
      </p>
    </div>
  );
}
