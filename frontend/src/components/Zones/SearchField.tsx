import { useEffect, useMemo, useState } from "react";
import { getStreets } from "../../api";

type Props = {
  onStreetChosen: (street: string) => void;
};

export function SearchField({ onStreetChosen }: Props) {
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

  return (
    <div className="relative">
      <label className="sr-only" htmlFor="street-search">
        Street parking search
      </label>
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
        placeholder="Search street rules (e.g. Victoria Avenue)"
        className="w-full rounded-xl border border-black/10 bg-white/95 px-4 py-3 text-sm shadow-md outline-none ring-park-fern/30 placeholder:text-park-slate focus:ring-2"
        autoComplete="off"
      />
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
