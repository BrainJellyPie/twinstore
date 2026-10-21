import { expect, it } from "vitest";
import { shopperGazeOffset } from "../shopperGaze";

it("holds fixations and transitions smoothly to the next one", () => {
  expect(shopperGazeOffset(0.2, 0)).toBe(shopperGazeOffset(1.7, 0));
  const before = shopperGazeOffset(1.8, 0);
  const after = shopperGazeOffset(1.89, 0);
  expect(after).not.toBe(before);
  expect(shopperGazeOffset(1.845, 0)).toBeCloseTo((before + after) / 2);
  expect(shopperGazeOffset(1.8 - 1e-6, 0)).toBeCloseTo(before);
  expect(shopperGazeOffset(2.4, 0)).toBe(after);
});

it("keeps distinct repeatable schedules within the small authored gaze range", () => {
  const schedule = (phase: number, vertical = false) => Array.from({ length: 1200 }, (_, i) => shopperGazeOffset(i / 60, phase, vertical));
  const horizontal = schedule(0.2), vertical = schedule(0.2, true);
  expect(horizontal).toEqual(schedule(0.2));
  expect(horizontal).not.toEqual(schedule(0.7));
  expect(Math.min(...horizontal)).toBeGreaterThanOrEqual(-0.3);
  expect(Math.max(...horizontal)).toBeLessThanOrEqual(0.3);
  expect(Math.min(...vertical)).toBeGreaterThanOrEqual(-0.16);
  expect(Math.max(...vertical)).toBeLessThanOrEqual(0.12);
});
