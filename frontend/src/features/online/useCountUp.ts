import { useEffect, useState } from "react";

/** A number that counts up from zero when it first shows (or changes), easing out; at once when motion is reduced. */
export function useCountUp(target: number, ms = 1200): number {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const start = performance.now();
    let frame = requestAnimationFrame(function tick(now) {
      const k = still ? 1 : Math.min(1, Math.max(0, now - start) / ms);
      setShown(target * (1 - (1 - k) ** 3));
      if (k < 1) frame = requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(frame);
  }, [target, ms]);
  return shown;
}
