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

type Props = {
  viewTime: Date | null;
  onViewTimeChange: (d: Date | null) => void;
  predictLoading?: boolean;
};

export function TimeScrubber({ viewTime, onViewTimeChange, predictLoading }: Props) {
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
          className="rounded-full bg-park-ink px-3 py-1 text-xs font-bold text-white"
          onClick={() => setPickerOpen((o) => !o)}
        >
          {formatChip(viewTime)}
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
      {predictLoading ? (
        <p className="mt-2 text-center text-[11px] text-park-slate">Updating predictions…</p>
      ) : null}
    </div>
  );
}
