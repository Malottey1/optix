// A media query as React state (false where matchMedia is missing, e.g. in tests).
import { useEffect, useState } from "react";

export function useMedia(query: string): boolean {
  const get = () =>
    typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(query).matches;
  const [on, setOn] = useState(get);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(query);
    const update = () => setOn(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [query]);
  return on;
}
