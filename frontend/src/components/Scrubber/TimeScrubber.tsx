import { useState } from "react";

const MAX_HOURS = 7 * 24;

function startOfHour(d: Date): Date {
  const x = new Date(d);
  x.setMinutes(0, 0, 0);
  x.setSeconds(0, 0);
  x.setMilliseconds(0);
  return x;
}

function addHours(base: Date, hours: number): Date {
  const x = new Date(base);
  x.setHours(x.getHours() + hours);
  return x;
}

function maxFuture(): Date {
  const x = new Date();
  x.setDate(x.getDate() + 7);
  return x;
}

function clampToRange(d: Date): Date {
  const lo = new Date();
  const hi = maxFuture();
  if (d < lo) return startOfHour(lo);
  if (d > hi) return startOfHour(hi);
  return startOfHour(d);
}

function formatChip(viewTime: Date | null): string {
  if (!viewTime) return "NOW";
  return new Intl.DateTimeFormat("en-AU", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Australia/Sydney",
  })
    .format(viewTime)
    .replace(/\./g, "")
    .toUpperCase();
}

function formatLoadingDateTime(viewTime: Date): string {
  return new Intl.DateTimeFormat("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Australia/Sydney",
    timeZoneName: "short",
  })
    .format(viewTime)
    .toUpperCase();
}

function hourOffset(viewTime: Date, base: Date): number {
  const deltaH = Math.round(
    (startOfHour(viewTime).getTime() - startOfHour(base).getTime()) / 3600000,
  );
  if (deltaH <= 0) return 1;
  return Math.min(MAX_HOURS, deltaH);
}

function formatForDatetimeLocal(d: Date): string {
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function Spinner() {
  return (
    <svg
      className="h-[13px] w-[13px] animate-spin text-park-fern"
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
  );
}

function LoadingSkeleton({ viewTime }: { viewTime: Date }) {
  const widths = ["68%", "82%", "51%", "74%"];
  const delays = [0, 0.13, 0.26, 0.39];

  return (
    <div className="mt-3 rounded-lg border border-park-fern/20 bg-park-mist/50 p-3">
      <div className="flex items-center gap-2">
        <Spinner />
        <span className="text-xs font-semibold text-park-fern">Calculating predictions</span>
      </div>
      <p className="mt-1 text-[10px] text-park-slate">
        {formatLoadingDateTime(viewTime)} · Sydney AEST
      </p>
      <div className="mt-2.5 h-[3px] overflow-hidden rounded-full bg-park-mist">
        <div className="relative h-full w-full">
          <div
            className="absolute h-full rounded-full bg-park-fern animate-ps-bar-slide"
            style={{ width: "40%" }}
          />
        </div>
      </div>
      <div className="mt-3 space-y-2">
        {widths.map((w, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className="h-2 rounded animate-ps-shimmer"
              style={{
                width: w,
                animationDelay: `${delays[i]}s`,
              }}
            />
            <span className="text-[10px] font-medium tabular-nums text-park-slate/50">
              {Math.round(30 + Math.random() * 60)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

type Props = {
  viewTime: Date | null;
  onViewTimeChange: (d: Date | null) => void;
  predictLoading?: boolean;
  isDesktop?: boolean;
};

export function TimeScrubber({ viewTime, onViewTimeChange, predictLoading, isDesktop = true }: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const base = startOfHour(new Date());
  const sliderVal = viewTime == null ? 0 : hourOffset(viewTime, base);

  const onSlider = (v: number) => {
    const n = Number(v);
    if (n <= 0) {
      onViewTimeChange(null);
      return;
    }
    onViewTimeChange(addHours(base, n));
  };

  const minLocal = formatForDatetimeLocal(new Date());
  const maxLocal = formatForDatetimeLocal(maxFuture());

  return (
    <div className="rounded-2xl bg-white/95 p-3 shadow-lg backdrop-blur-sm md:max-w-md">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-park-slate">
          Target time
        </span>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-full bg-park-ink px-3 py-1 text-xs font-bold text-white"
          onClick={() => setPickerOpen((o) => !o)}
        >
          {formatChip(viewTime)}
          {predictLoading && viewTime && !isDesktop ? (
            <span className="h-1.5 w-1.5 rounded-full bg-park-fern animate-pulse" />
          ) : null}
        </button>
      </div>
      <input
        type="range"
        min={0}
        max={MAX_HOURS}
        step={1}
        value={sliderVal}
        onChange={(e) => onSlider(Number(e.target.value))}
        className="mt-2 w-full accent-park-fern"
        aria-label="Scrub forecast hour"
      />
      <div className="mt-1 flex justify-between text-[10px] text-park-slate">
        <span>Now</span>
        <span>+7 days</span>
      </div>
      {pickerOpen ? (
        <div className="mt-3 border-t border-black/5 pt-3">
          <label className="block text-xs font-medium text-park-slate">Exact time</label>
          <input
            type="datetime-local"
            min={minLocal}
            max={maxLocal}
            className="mt-1 w-full rounded-lg border border-black/10 px-2 py-1.5 text-sm"
            onChange={(e) => {
              if (!e.target.value) return;
              const picked = new Date(e.target.value);
              if (!Number.isNaN(picked.getTime())) {
                onViewTimeChange(clampToRange(picked));
              }
            }}
          />
        </div>
      ) : null}
      {predictLoading && viewTime && isDesktop ? (
        <LoadingSkeleton viewTime={viewTime} />
      ) : null}
    </div>
  );
}
