/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { ALL_REALISTIC_CHARACTER_ASSETS } from "@/shared/utils/assetMap";
import { M } from "../constants";
import { shopperWalkTimeScale } from "../shopperGait";
import { positionBetweenEvents } from "../shopperPose";
import type { TimelineEvent } from "@/shared/types/domain";

const measurements = JSON.parse(readFileSync(resolve("public/assets/people/gait-sources.json"), "utf8")) as {
  revision: string; walks: Record<"female" | "male", { source: string; sha256: string; distance_metres: number }>;
};

it("measures the same pinned motion sources used by the bundled avatars", () => {
  const sources = JSON.parse(readFileSync(resolve("public/assets/people/sources.json"), "utf8")) as {
    revision: string; files: { source: string; sha256: string }[];
  };
  expect(measurements.revision).toBe(sources.revision);
  for (const record of Object.values(measurements.walks)) {
    expect(sources.files.find(file => file.source === record.source)?.sha256).toBe(record.sha256);
    expect(record.distance_metres).toBeGreaterThan(1);
    expect(record.distance_metres).toBeLessThan(2);
  }
});

it.each(ALL_REALISTIC_CHARACTER_ASSETS)("matches route distance over a captured walk cycle for %s", url => {
  const data = readFileSync(resolve("public", url.slice(1)));
  const model = JSON.parse(data.subarray(20, 20 + data.readUInt32LE(12)).toString()) as {
    animations: { name: string; samplers: { input: number }[] }[];
    accessors: { max: number[] }[];
  };
  const walk = model.animations.find(clip => clip.name === "walk")!;
  const duration = Math.max(...walk.samplers.map(sampler => model.accessors[sampler.input]!.max[0]!));
  const distance = measurements.walks[url.includes("/female-") ? "female" : "male"].distance_metres;
  for (const speed of [1 / 3, 0.5, 1]) {
    const rate = shopperWalkTimeScale(url, speed, 1, duration);
    const cycleWallSeconds = duration / rate;
    expect(speed * cycleWallSeconds).toBeCloseTo(distance * M, 7);
  }
});

it.each([60, 600, 3600, Number.MAX_VALUE])("bounds accelerated walking cadence at playback speed %s", speed => {
  expect(shopperWalkTimeScale("/assets/people/female-17.glb", 1, speed, 1.27)).toBe(1.75);
});

it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])("never produces invalid motion for speed %s", value => {
  expect(shopperWalkTimeScale("/assets/people/male-10.glb", value, 1, 1.1)).toBe(0);
  expect(shopperWalkTimeScale("/assets/people/male-10.glb", 1, value, 1.1)).toBe(0);
  expect(shopperWalkTimeScale("/assets/people/male-10.glb", 1, 1, value)).toBe(0);
});

it("retains normal preview playback and bounds very slow route movement", () => {
  expect(shopperWalkTimeScale("/assets/people/female-17.glb", undefined, 60, 1.27)).toBe(1);
  expect(shopperWalkTimeScale("/assets/characters/character-female-a.glb", 0.5, 1, 1)).toBe(1);
  expect(shopperWalkTimeScale("/assets/people/female-17.glb", 0.000001, 1, 1.27)).toBe(0.2);
});

const stop: TimelineEvent = { elapsed_sec: 2, x: 1, y: 1, action: "browse", duration: 10,
  target_rack: "shelf", face: "S", description: "", product_sku: "", product_name: "", price: 0 };
it.each([[1, 0], [0, 1], [-1, 0], [0, -1], [1, 1], [-1, -1]])("uses travel time after the stop for displacement (%s, %s)", (dx, dy) => {
  const next = { ...stop, elapsed_sec: 15, x: 1 + dx, y: 1 + dy, action: "move", duration: 0 };
  expect(positionBetweenEvents(stop, next, 11.999).speed).toBe(0);
  expect(positionBetweenEvents(stop, next, 12).speed).toBeCloseTo(Math.hypot(dx, dy) / 3);
  expect(positionBetweenEvents(stop, next, 13.5).speed).toBeCloseTo(Math.hypot(dx, dy) / 3);
});

it.each([10, 13, 20])("keeps stationary and exhausted segments at zero speed (dwell=%s)", duration => {
  const prev = { ...stop, duration };
  expect(positionBetweenEvents(prev, null, 30).speed).toBe(0);
  expect(positionBetweenEvents(prev, { ...prev, elapsed_sec: 15 }, 14).speed).toBe(0);
  if (duration >= 13) expect(positionBetweenEvents(prev, { ...prev, elapsed_sec: 15, x: 2 }, 14.999).speed).toBe(0);
});
