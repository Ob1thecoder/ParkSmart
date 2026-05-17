import { useEffect, useMemo, useState } from "react";
import { getStreets } from "../../api";

type Props = {
  onStreetChosen: (street: string) => void;
  onClear?: () => void;
};

function SearchIcon() {
  return (
    <svg
      className="h-4 w-4 text-park-slate/50"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function ClearButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-5 w-5 items-center justify-center rounded-full bg-park-slate/15 transition-colors hover:bg-park-slate/30"
      aria-label="Clear search"
    >
      <svg className="h-2 w-2 text-park-slate" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M1 1l6 6M7 1L1 7" />
      </svg>
    </button>
  );
}

export function SearchField({ onStreetChosen, onClear }: Props) {
  const [streets, setStreets] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    void getStreets().then(setStreets).catch(() => setStreets([]));
  }, []);

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return streets.slice(0, 12);
    return streets.filter((s) => s.toLowerCase().includes(t)).slice(0, 12);
  }, [streets, q]);

  const submit = (street: string) => {
    const s = street.trim();
    if (!s) return;
    onStreetChosen(s);
    setOpen(false);
  };

  const handleClear = () => {
    setQ("");
    onClear?.();
  };

  return (
    <div className="relative">
      <label className="sr-only" htmlFor="street-search">
        Street parking search
      </label>
      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2">
          <SearchIcon />
        </span>
        <input
          id="street-search"
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 180)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              const pick = filtered[0] ?? q;
              submit(pick);
            }
          }}
          placeholder="Search street rules…"
          className={`w-full rounded-xl border border-black/10 bg-white/95 py-3 pl-9 text-sm shadow-md outline-none ring-park-fern/30 placeholder:text-park-slate focus:ring-2 ${
            q ? "pr-10" : "pr-4"
          }`}
          autoComplete="off"
        />
        {q ? (
          <span className="absolute right-3 top-1/2 -translate-y-1/2">
            <ClearButton onClick={handleClear} />
          </span>
        ) : null}
      </div>
      {open && filtered.length > 0 ? (
        <ul className="absolute left-0 right-0 top-full z-[600] mt-1 max-h-48 overflow-auto rounded-xl border border-black/10 bg-white py-1 text-sm shadow-lg">
          {filtered.map((s) => (
            <li key={s}>
              <button
                type="button"
                className="block w-full px-4 py-2 text-left hover:bg-park-mist"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => submit(s)}
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
