import { StrictMode, useMemo } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { create, act } from "@react-three/test-renderer";
import { AssetPersona } from "../AssetPersona";
import { useSimulationStore } from "@/stores/simulationStore";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import type { TimelineEvent } from "@/shared/types/domain";

// Moving tracks detect phase resets as well as sudden changes in blend weights.
const clips = Object.entries({ idle: 1, wait: 2, walk: 10, browse: 20 }).map(([name, x]) =>
  new THREE.AnimationClip(name, 10, [
    new THREE.VectorKeyframeTrack("test-pose.position", [0, 10], [x, 0, 0, x + 1, 0, 0]),
    new THREE.QuaternionKeyframeTrack("test-pose.quaternion", [0, 10], [
      ...new THREE.Quaternion().setFromEuler(new THREE.Euler(x * 0.02, x * 0.04, -x * 0.01)).toArray(),
      ...new THREE.Quaternion().setFromEuler(new THREE.Euler(x * 0.03, x * 0.05, x * 0.02)).toArray(),
    ]),
  ]),
);
const originalWarn = console.warn;
vi.mock("@react-three/drei", async () => ({ ...await import("@react-three/drei/core/useAnimations.js"), Html: () => null }));
vi.mock("@/shared/hooks/useGlbModel", () => ({
  useGlbModel: () => {
    const clone = useMemo(() => { const root = new THREE.Group(), bone = new THREE.Bone(); bone.name = "test-pose"; root.add(bone); return root; }, []);
    return { clone, bbox: { size: new THREE.Vector3(0.4, 1.8, 0.3) }, offset: new THREE.Vector3(), animations: clips };
  },
}));
type Renderer = Awaited<ReturnType<typeof create>>;
const renderers: Renderer[] = [];
const browse: TimelineEvent = { elapsed_sec: 1, x: 0, y: 0, action: "browse", duration: 10, target_rack: "", face: "S", description: "", product_sku: "", product_name: "", price: 0 };
type Motion = "idle" | "walk" | "browse";
const person = (motion: Motion) => <AssetPersona personaId="blend-test" gender="Female" facing={0} isMoving={motion === "walk"} walkSpeed={0.08} color="#ddd" label="" event={motion === "browse" ? browse : null} />;
const pose = (renderer: Renderer) => renderer.scene.instance.getObjectByName("test-pose")!.position.x;
// Keyframe tracks store Float32 values; normalize before measuring angular error.
const rotation = (renderer: Renderer) => renderer.scene.instance.getObjectByName("test-pose")!.quaternion.clone().normalize();
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.spyOn(console, "warn").mockImplementation((message, ...args) => {
    if (message !== "THREE.THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.") originalWarn(message, ...args);
  });
  useSimulationStore.setState({ graphicsMode: "realistic" }); usePlaybackControlStore.getState().play();
});
afterEach(async () => {
  for (const renderer of renderers.splice(0)) await renderer.unmount();
  usePlaybackControlStore.getState().reset(); useSimulationStore.getState().reset(); vi.unstubAllGlobals(); vi.restoreAllMocks();
});

it.each([0, 0.01, 0.03, 0.075, 0.149])("starts a new action from the visible pose after %s seconds of an unfinished blend", async seconds => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2); await renderer.update(person("walk")); await renderer.advanceFrames(1, seconds);
  const before = pose(renderer), orientation = rotation(renderer); await renderer.update(person("browse"));
  expect(pose(renderer)).toBeCloseTo(before, 7);
  expect(rotation(renderer).angleTo(orientation)).toBeLessThan(1e-6);
});

it.each([0.01, 0.04, 0.1])("preserves the phase of an already contributing action when returning after %s seconds", async seconds => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  await renderer.update(person("walk")); await renderer.advanceFrames(1, seconds);
  await renderer.update(person("browse")); await renderer.advanceFrames(1, seconds);
  const before = pose(renderer), orientation = rotation(renderer); await renderer.update(person("walk"));
  expect(pose(renderer)).toBeCloseTo(before, 7);
  expect(rotation(renderer).angleTo(orientation)).toBeLessThan(1e-6);
});

it.each([1, 60, 3600] as const)("keeps rapid repeated transitions continuous in StrictMode at %s×", async speed => {
  usePlaybackControlStore.getState().setSpeed(speed);
  const renderer = await create(<StrictMode>{person("idle")}</StrictMode>); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  const motions: Motion[] = ["walk", "browse", "idle", "browse"];
  for (let i = 0; i < 40; i++) {
    const before = pose(renderer), orientation = rotation(renderer); await renderer.update(<StrictMode>{person(motions[i % motions.length]!)}</StrictMode>);
    expect(pose(renderer)).toBeCloseTo(before, 7);
    expect(rotation(renderer).angleTo(orientation)).toBeLessThan(1e-6);
    await renderer.advanceFrames(1, [0, 0.01, 0.04, 0.07][i % 4]!);
  }
});

it.each([Array<number>(30).fill(0.005), [0.15], [0, 0.03, 0.12]].map(deltas => ({ deltas })))("settles on the same target across frame schedules $deltas", async ({ deltas }) => {
  const renderer = await create(person("idle")), reference = await create(person("browse")); renderers.push(renderer, reference);
  await renderer.advanceFrames(1, 0.2); await renderer.update(person("walk")); await renderer.advanceFrames(1, 0.04);
  await renderer.update(person("browse"));
  for (const delta of deltas) await renderer.advanceFrames(1, delta);
  await reference.advanceFrames(1, 0.15);
  expect(pose(renderer)).toBeCloseTo(pose(reference), 6);
  expect(rotation(renderer).angleTo(rotation(reference))).toBeLessThan(1e-6);
});

it("holds a blend through pause and resumes without a pose jump", async () => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2); await renderer.update(person("walk")); await renderer.advanceFrames(1, 0.03);
  await renderer.update(person("browse")); await renderer.advanceFrames(1, 0.03);
  const before = pose(renderer);
  await act(async () => usePlaybackControlStore.getState().pause()); await renderer.advanceFrames(1, 10);
  expect(pose(renderer)).toBe(before);
  await act(async () => usePlaybackControlStore.getState().play()); await renderer.advanceFrames(1, 0);
  expect(pose(renderer)).toBeCloseTo(before, 7);
  await renderer.advanceFrames(1, 0.2); expect(pose(renderer)).toBeGreaterThan(before);
});
