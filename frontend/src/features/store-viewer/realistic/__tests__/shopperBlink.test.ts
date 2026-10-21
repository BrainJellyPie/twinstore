import { expect, it } from "vitest";
import { shopperBlinkWeight } from "../shopperBlink";

it("closes and reopens the authored eyelids without holding a squint between blinks", () => {
  const weights = Array.from({ length: 301 }, (_, i) => shopperBlinkWeight(i / 1000, 0));
  expect(weights[0]).toBe(0);
  expect(Math.min(...weights)).toBeGreaterThanOrEqual(0);
  expect(Math.max(...weights)).toBe(1);
  expect(weights[40]).toBeGreaterThan(weights[10]!);
  expect(weights[170]).toBeLessThan(weights[120]!);
  expect(weights.slice(230).every((weight) => weight === 0)).toBe(true);
  expect(shopperBlinkWeight(3.28, 0)).toBe(1);
});

it("gives different shoppers distinct repeatable blink schedules", () => {
  const schedule = (phase: number) => Array.from({ length: 300 }, (_, i) => shopperBlinkWeight(i / 30, phase));
  const first = schedule(0.2), second = schedule(0.7);
  expect(first).toEqual(schedule(0.2));
  expect(first).not.toEqual(second);
  expect(first.some((weight) => weight > 0.9)).toBe(true);
  expect(second.some((weight) => weight > 0.9)).toBe(true);
});
