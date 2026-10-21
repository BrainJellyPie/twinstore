import { StrictMode, useMemo } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { create, act } from "@react-three/test-renderer";
import { AssetPersona } from "../AssetPersona";
import { useSimulationStore } from "@/stores/simulationStore";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import type { TimelineEvent } from "@/shared/types/domain";

const positions = { idle: 1, wait: 2, walk: 10, browse: 20 };
const clips = Object.entries(positions).map(([name, x]) => new THREE.AnimationClip(name, 1, [
  new THREE.VectorKeyframeTrack("test-pose.position", [0, 1], [x, 0, 0, x, 0, 0]),
]));
const originalWarn = console.warn;
// Use the real ESM hook so its Three classes match the test scene.
vi.mock("@react-three/drei", async () => ({
  ...await import("@react-three/drei/core/useAnimations.js"), Html: () => null,
}));
vi.mock("@/shared/hooks/useGlbModel", () => ({
  useGlbModel: () => {
    const clone = useMemo(() => {
      const root = new THREE.Group(), bone = new THREE.Bone(); bone.name = "test-pose"; root.add(bone); return root;
    }, []);
    return { clone, bbox: { size: new THREE.Vector3(0.4, 1.8, 0.3) }, offset: new THREE.Vector3(), animations: clips };
  },
}));
type Renderer = Awaited<ReturnType<typeof create>>;
const renderers: Renderer[] = [];
const browse: TimelineEvent = { elapsed_sec: 1, x: 0, y: 0, action: "browse", duration: 10, target_rack: "", face: "S", description: "", product_sku: "", product_name: "", price: 0 };
const person = (motion: "idle" | "walk" | "browse", id = "pose-test") => <AssetPersona personaId={id} gender="Female" facing={0} isMoving={motion === "walk"} color="#ddd" label="" event={motion === "browse" ? browse : null} />;
const pose = (renderer: Renderer) => renderer.scene.instance.getObjectByName("test-pose")!.position.x;
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

it.each(([1, 60, 3600] as const).flatMap(speed =>
  [0, 0.01, 0.03, 0.075, 0.149, 0.15, 0.5].map(seconds => ({ speed, seconds })),
))("applies a paused browse pose after $seconds seconds at $speed×", async ({ speed, seconds }) => {
  usePlaybackControlStore.getState().setSpeed(speed);
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  await renderer.update(person("walk")); await renderer.advanceFrames(1, seconds);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.update(person("browse"));
  expect(pose(renderer)).toBeCloseTo(positions.browse, 7);
  await renderer.advanceFrames(1, 20);
  expect(pose(renderer)).toBeCloseTo(positions.browse, 7);
});

it.each([0, 0.025, 0.1])("applies a paused walk pose after %s seconds of a browse transition", async seconds => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  await renderer.update(person("browse")); await renderer.advanceFrames(1, seconds);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.update(person("walk"));
  expect(pose(renderer)).toBeCloseTo(positions.walk, 7);
});

it("freezes the current blend on pause and continues that blend on resume", async () => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  const standing = pose(renderer);
  await renderer.update(person("walk")); await renderer.advanceFrames(1, 0.05);
  const blended = pose(renderer);
  expect(blended).toBeGreaterThan(standing); expect(blended).toBeLessThan(positions.walk);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.advanceFrames(1, 10); expect(pose(renderer)).toBe(blended);
  await act(async () => usePlaybackControlStore.getState().play());
  await renderer.advanceFrames(1, 0.2); expect(pose(renderer)).toBeCloseTo(positions.walk, 7);
});

it("clears earlier actions after several interrupted transitions and repeated paused seeks", async () => {
  const renderer = await create(<StrictMode>{person("idle")}</StrictMode>); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  for (const motion of ["walk", "browse", "idle", "walk"] as const) {
    await renderer.update(<StrictMode>{person(motion)}</StrictMode>); await renderer.advanceFrames(1, 0.02);
  }
  await act(async () => usePlaybackControlStore.getState().pause());
  for (const motion of ["browse", "walk", "browse", "walk"] as const) {
    await renderer.update(<StrictMode>{person(motion)}</StrictMode>);
    expect(pose(renderer)).toBeCloseTo(positions[motion], 7);
  }
  await act(async () => usePlaybackControlStore.getState().play());
  await renderer.update(<StrictMode>{person("browse")}</StrictMode>); await renderer.advanceFrames(1, 0.2);
  expect(pose(renderer)).toBeCloseTo(positions.browse, 7);
});


it.each(["walk", "browse"] as const)("applies a newly mounted paused %s pose immediately", async motion => {
  usePlaybackControlStore.getState().pause();
  const renderer = await create(<StrictMode>{person(motion)}</StrictMode>); renderers.push(renderer);
  expect(pose(renderer)).toBeCloseTo(positions[motion], 7);
  await renderer.update(<></>); await renderer.update(<StrictMode>{person(motion)}</StrictMode>);
  expect(pose(renderer)).toBeCloseTo(positions[motion], 7);
});

it("returns to the selected standing pose during a paused seek", async () => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2); const standing = pose(renderer);
  await renderer.update(person("walk")); await renderer.advanceFrames(1, 0.025);
  await renderer.update(person("browse")); await renderer.advanceFrames(1, 0.025);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.update(person("idle"));
  expect(pose(renderer)).toBeCloseTo(standing, 7);
});

it("removes an old blend when a paused shopper changes identity on the same action", async () => {
  const renderer = await create(person("idle")); renderers.push(renderer);
  await renderer.advanceFrames(1, 0.2);
  await renderer.update(person("browse")); await renderer.advanceFrames(1, 0.025);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.update(person("browse", "next-pose-test"));
  expect(pose(renderer)).toBeCloseTo(positions.browse, 7);
});
