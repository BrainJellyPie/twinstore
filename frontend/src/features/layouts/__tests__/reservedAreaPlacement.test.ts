import { expect, it } from "vitest";
import { AREA_POSITIONS, moveReservedArea, swapReservedAreaDimensions } from "../reservedAreaPlacement";

const area = Object.freeze({ label: "Consultation", x: 2, y: 3, width: 4, height: 3 });
it.each([
  ["back_left", 1, 1], ["back_right", 19, 1], ["front_left", 1, 14], ["front_right", 19, 14], ["center", 10, 7],
] as const)("moves to %s without changing name or dimensions", (position, x, y) => {
  expect(moveReservedArea(area, [24, 18], position)).toEqual({ ...area, x, y });
  expect(area).toEqual({ label: "Consultation", x: 2, y: 3, width: 4, height: 3 });
});

it.each([[8, 6], [9, 7], [8, 40], [40, 6], [40, 40], [24, 18]] as [number, number][])("fits every anchor and exact interior boundary on %ix%i", (width, height) => {
  for (const [w, h] of [[1, 1], [4, 3], [width - 2, height - 2]]) {
    const original = { ...area, width: w!, height: h! };
    for (const [position] of AREA_POSITIONS) {
      const moved = moveReservedArea(original, [width, height], position)!;
      expect(moved.x).toBeGreaterThanOrEqual(1); expect(moved.y).toBeGreaterThanOrEqual(1);
      expect(moved.x + moved.width).toBeLessThanOrEqual(width - 1);
      expect(moved.y + moved.height).toBeLessThanOrEqual(height - 1);
      expect(moveReservedArea(moved, [width, height], position)).toEqual(moved);
      expect(moved.width * moved.height).toBe(w! * h!);
    }
  }
});

it.each([[7, 6], [8, 5], [41, 40], [40, 41], [8.5, 6], [8, NaN], [Infinity, 40]] as [number, number][])("rejects invalid grid %s x %s", (width, height) => {
  expect(moveReservedArea(area, [width, height], "center")).toBeNull();
  expect(swapReservedAreaDimensions(area, [width, height])).toBeNull();
});
it.each([0, -1, 1.5, NaN, Infinity, 39])("rejects invalid or oversized width %s without shrinking it", (width) => {
  expect(moveReservedArea({ ...area, width }, [40, 40], "center")).toBeNull();
  expect(swapReservedAreaDimensions({ ...area, width }, [40, 40])).toBeNull();
});
it("recovers invalid coordinates by moving a valid-sized area", () => {
  expect(moveReservedArea({ ...area, x: NaN, y: Infinity }, [8, 6], "back_right")).toEqual({ ...area, x: 3, y: 1 });
});
it.each([[4, 3], [3, 4], [1, 38], [38, 1], [3, 3]] as const)("swaps %ix%i twice without moving or shrinking the rectangle", (width, height) => {
  const original = { ...area, x: 1, y: 1, width, height };
  const swapped = swapReservedAreaDimensions(original, [40, 40])!;
  expect(swapped).toEqual({ ...original, width: height, height: width });
  expect(swapReservedAreaDimensions(swapped, [40, 40])).toEqual(original);
});
it("does not shift an area away from an edge to fit a swap, but permits deliberate repositioning", () => {
  const edge = { ...area, x: 1, y: 2 };
  expect(swapReservedAreaDimensions(edge, [8, 6])).toBeNull();
  const moved = moveReservedArea(edge, [8, 6], "back_left")!;
  expect(swapReservedAreaDimensions(moved, [8, 6])).toEqual({ ...moved, width: 3, height: 4 });
});
it("can recover an oversized orientation when its swapped dimensions fit at the current position", () => {
  expect(swapReservedAreaDimensions({ ...area, x: 1, y: 1, width: 4, height: 6 }, [8, 6])).toEqual({ ...area, x: 1, y: 1, width: 6, height: 4 });
});
