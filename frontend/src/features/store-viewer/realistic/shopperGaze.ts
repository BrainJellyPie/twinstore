// Small cosmetic fixation changes, independent of simulated shopping decisions.
// Most time is spent holding a gaze; each transition lasts 90 ms of playback wall time.
export function shopperGazeOffset(elapsedSeconds: number, phase: number, vertical = false): number {
  const period = 1.8 + phase * 1.4;
  const time = elapsedSeconds + phase * period;
  const fixation = Math.floor(time / period);
  const u = Math.min((time % period) / 0.09, 1);
  const blend = u * u * (3 - 2 * u);
  const frequency = vertical ? 1.618 : 2.39996;
  const shift = phase * (vertical ? 21.37 : 17.71);
  const previous = Math.sin((fixation - 1) * frequency + shift);
  const next = Math.sin(fixation * frequency + shift);
  // Use only a small part of the authored eye range, with a slight downward bias.
  return (previous + (next - previous) * blend) * (vertical ? 0.14 : 0.3) - (vertical ? 0.02 : 0);
}
