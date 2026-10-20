// Sequential color ramps for floor heatmaps, shared by the 3D overlay and the legend.

export type HeatmapPalette = "footfall" | "dwell" | "traffic";

export type Rgb = [number, number, number];

// Sequential color ramps (ColorBrewer YlOrRd / RdPu / Blues), low → high.
export const RAMPS: Record<HeatmapPalette, Rgb[]> = {
  footfall: [[255, 237, 160], [254, 178, 76], [240, 59, 32], [189, 0, 38]],
  dwell: [[252, 197, 192], [247, 104, 161], [174, 1, 126], [73, 0, 106]],
  traffic: [[198, 219, 239], [107, 174, 214], [33, 113, 181], [8, 48, 107]],
};

export function ramp(stops: Rgb[], t: number): Rgb {
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  const a = stops[i]!;
  const b = stops[i + 1]!;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

// CSS gradient matching a palette, for the on-screen legend.
export function paletteGradient(palette: HeatmapPalette): string {
  const stops = RAMPS[palette].map(([r, g, b], i, arr) => `rgb(${r} ${g} ${b}) ${(i / (arr.length - 1)) * 100}%`);
  return `linear-gradient(to right, ${stops.join(", ")})`;
}
