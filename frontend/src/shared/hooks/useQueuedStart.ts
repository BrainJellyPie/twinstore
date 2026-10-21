import { useCallback, useEffect, useState } from "react";

/**
 * Starts `start(value)` on the render after `queue(value)`, never inside a mount effect: React's StrictMode runs
 * mount effects twice, which would send a request twice, or start it on a mutation observer that is then detached so
 * the result never shows. Several queue calls before that render start once, with the last value.
 */
export function useQueuedStart<T>(start: (value: T) => void): (value: T) => void {
  const [queued, setQueued] = useState<{ value: T } | null>(null);
  useEffect(() => {
    if (queued === null) return;
    setQueued(null);
    start(queued.value);
  }, [queued, start]);
  return useCallback((value: T) => setQueued({ value }), []);
}
