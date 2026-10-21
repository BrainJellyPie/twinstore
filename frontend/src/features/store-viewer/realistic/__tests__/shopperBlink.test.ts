import { expect, it } from "vitest";
import { shopperBlinkWeight } from "../shopperBlink";

it("closes and reopens the authored eyelids without holding a squint between blinks", () => {
  const weights = Array.from({ length: 301 }, (_, i) => shopperBlinkWeight(0.25 + i / 1000, 0));
  expect(weights[0]).toBe(0);
  expect(Math.min(...weights)).toBeGreaterThanOrEqual(0);
  expect(Math.max(...weights)).toBe(1);
  expect(weights[40]).toBeGreaterThan(weights[10]!);
  expect(weights[170]).toBeLessThan(weights[120]!);
  expect(weights.slice(230).every((weight) => weight === 0)).toBe(true);
});

it("gives different shoppers distinct repeatable blink schedules", () => {
  const schedule = (phase: number) => Array.from({ length: 1800 }, (_, i) => shopperBlinkWeight(i / 30, phase));
  const first = schedule(0.2), second = schedule(0.7);
  expect(first).toEqual(schedule(0.2));
  expect(first).not.toEqual(second);
  expect(first.some((weight) => weight > 0.9)).toBe(true);
  expect(second.some((weight) => weight > 0.9)).toBe(true);
});

const phases = [...Array.from({ length: 16 }, (_, i) => i / 16), 1 - 1 / 0x100000000];
it.each(phases)("varies intervals while preserving complete, separate blinks at phase %s", (phase) => {
  const starts: number[] = [], blinks: number[][] = [];
  let previous = 0;
  for (let i = 0; i < 24000; i++) {
    const time = i * 0.005, weight = shopperBlinkWeight(time, phase);
    if (weight > 0 && previous === 0) { starts.push(time); blinks.push([]); }
    if (weight > 0) blinks[blinks.length - 1]!.push(weight);
    previous = weight;
  }
  // Discard possible partial blinks at the beginning and end of the sample.
  for (const blink of blinks.slice(1, -1)) {
    expect(blink.length).toBeGreaterThanOrEqual(45);
    expect(blink.length).toBeLessThanOrEqual(47);
    expect(Math.min(...blink)).toBeGreaterThan(0);
    expect(Math.max(...blink)).toBe(1);
    const peak = blink.indexOf(1);
    expect(blink.slice(1, peak + 1).every((v, i) => v >= blink[i]!)).toBe(true);
    expect(blink.slice(peak + 1).every((v, i) => v <= blink[peak + i]!)).toBe(true);
  }
  const intervals = starts.slice(2).map((time, i) => time - starts[i + 1]!);
  expect(Math.min(...intervals)).toBeGreaterThanOrEqual(0.34);
  expect(Math.max(...intervals)).toBeLessThan(12);
  expect(new Set(intervals.map(v => Math.round(v * 100))).size).toBeGreaterThan(8);
});

it("occasionally follows a blink with a distinct second blink", () => {
  const starts: number[] = [];
  let previous = 0;
  for (let i = 0; i < 60000; i++) {
    const weight = shopperBlinkWeight(i * 0.005, 0.2);
    if (weight > 0 && previous === 0) starts.push(i * 0.005);
    previous = weight;
  }
  const intervals = starts.slice(1).map((time, i) => time - starts[i]!);
  expect(intervals.some(gap => gap > 0.34 && gap < 0.36)).toBe(true);
  expect(intervals.filter(gap => gap < 0.5).length).toBeLessThan(intervals.length / 3);
});

it.each(phases)("stays open at window seams and bounded after long gaps at phase %s", (phase) => {
  const period = 3.2 + phase * 2.8;
  for (const cycle of [1, 2, 100, 10000, 1000000]) {
    const boundary = (cycle - phase) * period;
    for (const offset of [-0.000001, 0, 0.000001]) expect(shopperBlinkWeight(boundary + offset, phase)).toBe(0);
    const weight = shopperBlinkWeight(boundary + period / 2, phase);
    expect(Number.isFinite(weight)).toBe(true);
    expect(weight).toBeGreaterThanOrEqual(0);
    expect(weight).toBeLessThanOrEqual(1);
  }
});
