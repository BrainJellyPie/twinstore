// Cosmetic motion uses playback wall time, so accelerated simulation does not
// make eyelids strobe. The stable per-shopper phase also varies blink intervals.
export function shopperBlinkWeight(elapsedSeconds: number, phase: number): number {
  const period = 3.2 + phase * 2.8;
  const t = (elapsedSeconds + phase * period) % period;
  if (t >= 0.23) return 0;
  if (t < 0.075) {
    const u = t / 0.075;
    return u * u * (3 - 2 * u);
  }
  if (t < 0.105) return 1;
  const u = (t - 0.105) / 0.125;
  return 1 - u * u * (3 - 2 * u);
}
