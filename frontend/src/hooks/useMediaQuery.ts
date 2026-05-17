import { useEffect, useState } from "react";

function getMatch(query: string): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia(query).matches;
}

/**
 * Tracks a CSS media query. Initial state reads `window` synchronously so the
 * first paint matches wide viewports (avoids treating desktop as mobile before
 * effects run — which broke layout / assistant visibility).
 */
export function useMediaQuery(query: string): boolean {
  const [match, setMatch] = useState(() => getMatch(query));

  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);

  return match;
}
