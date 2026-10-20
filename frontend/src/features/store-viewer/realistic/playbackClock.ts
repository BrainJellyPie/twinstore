// Mirrors the playback loop's clock (which lives in a ref inside
// useSimulationLoop) from the public stores: integrates delta × speed while
// playing and re-anchors on the minute the loop publishes. Pure step function.

export interface ClockState {
  t: number;
  day: number;
  minute: number;
}

export interface ClockInputs {
  playing: boolean;
  speed: number;
  day: number;
  currentMinute: number;
  finished: boolean;
  minTime: number;
  maxTime: number;
}

export function createClock(): ClockState {
  return { t: Number.NaN, day: -1, minute: Number.NaN };
}

export function stepClock(c: ClockState, delta: number, inp: ClockInputs): number {
  if (Number.isNaN(c.t) || c.day !== inp.day) {
    c.day = inp.day;
    c.minute = inp.currentMinute;
    c.t = Math.max(inp.minTime, inp.currentMinute);
    return c.t;
  }
  const step = inp.playing && !inp.finished ? Math.max(0, delta) * inp.speed : 0;
  c.t += step;
  if (inp.currentMinute !== c.minute) c.minute = inp.currentMinute;
  // The loop's time is always inside the published minute (one frame of slack
  // because the two useFrame callbacks may run in either order).
  const lo = inp.currentMinute;
  const hi = inp.currentMinute + 60 + step;
  if (c.t < lo) c.t = lo;
  if (c.t > hi) c.t = hi;
  if (inp.finished) c.t = inp.maxTime;
  c.t = Math.min(c.t, inp.maxTime);
  return c.t;
}
