import type { Rack } from "@/shared/types/domain";

// The footprint includes chairs on both long sides. A one-cell-deep table has
// no chairs, matching the furniture shown in Classic and Realistic views.
export function diningSeats(width: number, depth: number): number {
  if (depth < 1.8 || width < 0.8) return 0;
  return width >= 2.8 ? 6 : width >= 1.8 ? 4 : 2;
}

export function rackDiningSeats(rack: Pick<Rack, "type" | "shape">): number {
  return rack.type === "table" ? diningSeats(Math.max(0, ...rack.shape.map((row) => row.length)), rack.shape.length) : 0;
}
