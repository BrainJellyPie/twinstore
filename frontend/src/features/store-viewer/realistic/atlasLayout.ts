// Texture-atlas grid math shared by the label, price-tag and sign atlases.
// Pure — the canvas drawing lives in canvasArt.ts.

export interface AtlasGrid {
  cols: number;
  rows: number;
  cellW: number; // px
  cellH: number; // px
  width: number; // px
  height: number; // px
}

const MAX_TEXTURE = 4096;

function pow2(n: number): number {
  let p = 1;
  while (p < n) p *= 2;
  return p;
}

// Square-ish grid that fits `count` cells of aspect cellW:cellH, shrinking the
// cells when needed so the texture stays within MAX_TEXTURE.
export function atlasGrid(count: number, cellW = 128, cellH = cellW, maxSize = MAX_TEXTURE): AtlasGrid {
  const n = Math.max(1, count);
  const aspect = cellW / cellH;
  let cols = Math.max(1, Math.ceil(Math.sqrt(n / aspect)));
  let rows = Math.ceil(n / cols);
  let cw = cellW;
  let ch = cellH;
  const scale = Math.min(1, maxSize / (cols * cw), maxSize / (rows * ch));
  if (scale < 1) {
    cw = Math.max(8, Math.floor(cw * scale));
    ch = Math.max(8, Math.floor(ch * scale));
    cols = Math.max(1, Math.floor(maxSize / cw));
    rows = Math.ceil(n / cols);
  }
  return { cols, rows, cellW: cw, cellH: ch, width: pow2(cols * cw), height: pow2(rows * ch) };
}

// Pixel origin (top-left) of a cell.
export function cellPixel(grid: AtlasGrid, index: number): [number, number] {
  const col = index % grid.cols;
  const row = Math.floor(index / grid.cols);
  return [col * grid.cellW, row * grid.cellH];
}

// UV offset (bottom-left corner, flipY texture convention) and scale of a cell.
// A local uv in [0,1]² maps to offset + uv * scale.
export function cellUv(grid: AtlasGrid, index: number): { offset: [number, number]; scale: [number, number] } {
  const [px, py] = cellPixel(grid, index);
  const su = grid.cellW / grid.width;
  const sv = grid.cellH / grid.height;
  return {
    offset: [px / grid.width, 1 - (py + grid.cellH) / grid.height],
    scale: [su, sv],
  };
}

// Zones inside every product label cell (local uv). The narrow strip on the left
// holds flat colours so caps, sides and backs can sample a solid colour from the
// same texture as the printed label.
export const LABEL_U0 = 0.1;
export const ZONE_BODY: [number, number] = [0.035, 0.25];
export const ZONE_ACCENT: [number, number] = [0.035, 0.75];
