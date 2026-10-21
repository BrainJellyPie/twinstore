function blinkNoise(cycle: number, phase: number, salt: number): number {
  let value = (cycle + phase * 0x100000000 + salt) >>> 0;
  value = Math.imul(value ^ (value >>> 16), 0x21f0aaad);
  value = Math.imul(value ^ (value >>> 15), 0x735a2d97);
  return ((value ^ (value >>> 15)) >>> 0) / 0x100000000;
}

function eyelidWeight(t: number): number {
  if (t < 0 || t >= 0.23) return 0;
  if (t < 0.075) {
    const u = t / 0.075;
    return u * u * (3 - 2 * u);
  }
  if (t < 0.105) return 1;
  const u = (t - 0.105) / 0.125;
  return 1 - u * u * (3 - 2 * u);
}

// Cosmetic motion uses playback wall time, so accelerated simulation does not
// make eyelids strobe. Vary the onset within each shopper's time windows rather
// than repeating one interval; occasionally follow with a second, separate blink.
export function shopperBlinkWeight(elapsedSeconds: number, phase: number): number {
  const period = 3.2 + phase * 2.8;
  const time = elapsedSeconds + phase * period;
  const cycle = Math.floor(time / period);
  const onset = 0.25 + blinkNoise(cycle, phase, 0) * (period - 0.9);
  const t = time - cycle * period - onset;
  const first = eyelidWeight(t);
  const second = blinkNoise(cycle, phase, 0x9e3779b9) < 0.14 ? eyelidWeight(t - 0.35) : 0;
  return Math.max(first, second);
}
