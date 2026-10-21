import { expect, it } from "vitest";
import { resolveFloorSize } from "../templateOptions";

const format = { grid: [30, 24] as [number, number] };

it("resolves blank and partial dimensions against the source format", () => {
  expect(resolveFloorSize({}, format)).toEqual({ width: 30, height: 24 });
  expect(resolveFloorSize({ width: 20 }, format)).toEqual({ width: 20, height: 24 });
  expect(resolveFloorSize({ height: 18 }, format)).toEqual({ width: 30, height: 18 });
  expect(resolveFloorSize({ width: null, height: null }, format)).toEqual({ width: 30, height: 24 });
  expect(resolveFloorSize({}, undefined)).toBeNull();
});

it.each([[8, 6], [8, 40], [40, 6], [40, 40]])("accepts boundary size %i×%i", (width, height) => {
  expect(resolveFloorSize({ width, height }, format)).toEqual({ width, height });
});

it.each([
  { width: 0 }, { width: 7 }, { width: 41 }, { width: -1 }, { width: 12.5 }, { width: NaN }, { width: Infinity },
  { height: 0 }, { height: 5 }, { height: 41 }, { height: -1 }, { height: 12.5 }, { height: NaN }, { height: Infinity },
])("rejects invalid dimensions before sharing: %j", (patch) => {
  expect(resolveFloorSize(patch, format)).toBeNull();
});
