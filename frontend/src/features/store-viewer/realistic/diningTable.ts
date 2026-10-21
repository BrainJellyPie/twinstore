// Shared furniture proportions for Classic and Realistic views. All parts stay
// inside the fixture footprint, so displayed chairs agree with path obstacles.
export interface TablePart {
  material: "wood" | "metalGrey";
  position: [number, number, number];
  size: [number, number, number];
}

export function diningTableParts(width: number, depth: number): TablePart[] {
  const w = Math.min(1.25, width - 0.12);
  const d = Math.min(0.72, depth - 0.12);
  const parts: TablePart[] = [];
  const box = (material: TablePart["material"], x: number, y: number, z: number, sx: number, sy: number, sz: number) => {
    parts.push({ material, position: [x, y, z], size: [sx, sy, sz] });
  };
  box("wood", 0, 0.72, 0, w, 0.04, d);
  for (const x of [-w / 2 + 0.06, w / 2 - 0.06]) {
    for (const z of [-d / 2 + 0.06, d / 2 - 0.06]) box("metalGrey", x, 0.35, z, 0.045, 0.7, 0.045);
  }
  if (width >= 1.8 && depth >= 1.8) {
    for (const x of [-0.34, 0.34]) {
      for (const side of [-1, 1]) {
        const z = side * 0.69;
        box("wood", x, 0.43, z, 0.4, 0.04, 0.38);
        box("wood", x, 0.67, z + side * 0.17, 0.4, 0.42, 0.04);
        for (const dx of [-0.15, 0.15]) {
          for (const dz of [-0.14, 0.14]) box("metalGrey", x + dx, 0.205, z + dz, 0.03, 0.41, 0.03);
        }
      }
    }
  }
  return parts;
}
