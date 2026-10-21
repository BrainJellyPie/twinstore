export const MIN_DIM = 5;
export const MAX_DIM = 40;

export function clampDim(value: number): number {
  if (Number.isNaN(value)) return MIN_DIM;
  return Math.max(MIN_DIM, Math.min(MAX_DIM, Math.round(value)));
}
