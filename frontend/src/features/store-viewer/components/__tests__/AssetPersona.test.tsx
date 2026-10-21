import { StrictMode, useMemo } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { create, act } from "@react-three/test-renderer";
import { AssetPersona } from "../AssetPersona";
import { useSimulationStore } from "@/stores/simulationStore";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { characterAnimationPhase } from "@/shared/utils/assetMap";
import { shopperBlinkWeight } from "../../realistic/shopperBlink";

const testFaces = new Set<THREE.Mesh>();
const originalWarn = console.warn;

vi.mock("@react-three/drei", async original => ({
  ...await original<typeof import("@react-three/drei")>(),
  Html: () => null,
}));
vi.mock("@/shared/hooks/useGlbModel", () => ({
  useGlbModel: () => {
    const clone = useMemo(() => {
      const root = new THREE.Group();
      const face = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 0.2), new THREE.MeshBasicMaterial());
      face.name = "test-face";
      face.morphTargetDictionary = { blink: 0, lookLeft: 1, lookRight: 2, lookUp: 3, lookDown: 4 };
      face.morphTargetInfluences = [0, 0, 0, 0, 0];
      testFaces.add(face);
      root.add(face);
      return root;
    }, []);
    return { clone, bbox: { size: new THREE.Vector3(0.4, 1.8, 0.3) }, offset: new THREE.Vector3(), animations: [] };
  },
}));

type Renderer = Awaited<ReturnType<typeof create>>;
const renderers: Renderer[] = [];
const person = (facing: number) => <AssetPersona personaId="shopper-test" gender="Female" facing={facing} isMoving={false} color="#ddd" label="" event={null} />;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  // R3F's test root creates a Clock even though these tests supply frame deltas.
  vi.spyOn(console, "warn").mockImplementation((message, ...args) => {
    if (message !== "THREE.THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.") originalWarn(message, ...args);
  });
  useSimulationStore.setState({ graphicsMode: "realistic" });
  usePlaybackControlStore.getState().play();
});
afterEach(async () => {
  for (const renderer of renderers.splice(0)) await renderer.unmount();
  for (const face of testFaces) {
    face.geometry.dispose();
    for (const material of Array.isArray(face.material) ? face.material : [face.material]) material.dispose();
  }
  testFaces.clear();
  usePlaybackControlStore.getState().reset();
  useSimulationStore.getState().reset();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("turns by elapsed time even when one frame lasts half a second", async () => {
  const renderer = await create(person(0)); renderers.push(renderer);
  await renderer.advanceFrames(1, 0);
  await renderer.update(person(Math.PI / 2));
  await act(async () => { await renderer.advanceFrames(1, 0.5); });
  const heading = renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y;
  expect(heading).toBeCloseTo(Math.PI / 2 * (1 - Math.exp(-12 * 0.5)), 8);
});

const schedules = [Array<number>(30).fill(1 / 60), [0.5], [0.02, 0.18, 0.3]];
it.each([
  [0, Math.PI / 2], [Math.PI / 2, 0], [Math.PI - 0.02, -Math.PI + 0.02],
  [-Math.PI + 0.02, Math.PI - 0.02], [1, 1],
])("takes the same turn from %s to %s across frame schedules", async (start, target) => {
  const results: number[] = [];
  for (const deltas of schedules) {
    const renderer = await create(person(start)); renderers.push(renderer);
    await renderer.advanceFrames(1, 0);
    await renderer.update(person(target));
    for (const delta of deltas) await renderer.advanceFrames(1, delta);
    results.push(renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y);
  }
  for (const result of results.slice(1)) expect(result).toBeCloseTo(results[0]!, 8);
});

it.each([1, -1])("crosses the signed half-turn boundary along the short path (%s)", async sign => {
  const start = sign * (Math.PI - 0.02), target = -start;
  const renderer = await create(person(start)); renderers.push(renderer);
  await renderer.advanceFrames(1, 0);
  await renderer.update(person(target));
  await renderer.advanceFrames(1, 0.03);
  const heading = renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y;
  expect((heading - start) * sign).toBeGreaterThan(0);
  expect(Math.abs(heading - start)).toBeLessThan(0.04);
  await renderer.advanceFrames(1, 5);
  const settled = renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y;
  expect(Math.sin(settled - target)).toBeCloseTo(0, 10);
});

it("holds a zero-delta frame, snaps while paused, and resumes smoothly", async () => {
  const renderer = await create(person(0)); renderers.push(renderer);
  await renderer.advanceFrames(1, 0);
  await renderer.update(person(1));
  await renderer.advanceFrames(1, 0);
  expect(renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y).toBe(0);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.advanceFrames(1, 0.5);
  expect(renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y).toBe(1);
  await act(async () => usePlaybackControlStore.getState().play());
  await renderer.update(person(0));
  await renderer.advanceFrames(1, 0.5);
  expect(renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y).toBeCloseTo(Math.exp(-6), 8);
});

function facialWeights(renderer: Renderer) {
  const face = renderer.scene.instance.getObjectByName("test-face");
  if (!(face instanceof THREE.Mesh)) throw new Error("Missing test face");
  return [...face.morphTargetInfluences!];
}

it("keeps actual facial morphs independent of frame spacing and playback speed", async () => {
  const results: number[][] = [];
  for (const speed of [1, 60, 3600] as const) for (const deltas of [Array<number>(360).fill(1 / 60), Array<number>(12).fill(0.5), [0.02, 0.98, 1.5, 0.1, 0.4, 3]]) {
    await act(async () => usePlaybackControlStore.getState().setSpeed(speed));
    const renderer = await create(person(0)); renderers.push(renderer);
    for (const delta of deltas) await renderer.advanceFrames(1, delta);
    results.push(facialWeights(renderer));
  }
  expect(results[0]!.some(weight => weight !== 0)).toBe(true);
  for (const result of results.slice(1)) result.forEach((weight, i) => expect(weight).toBeCloseTo(results[0]![i]!, 8));
});

it("freezes facial morphs while paused and clears old time on remount", async () => {
  const renderer = await create(person(0)); renderers.push(renderer);
  await renderer.advanceFrames(1, 3);
  const before = facialWeights(renderer);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.advanceFrames(1, 30);
  expect(facialWeights(renderer)).toEqual(before);
  await renderer.update(<></>);
  await renderer.update(person(0));
  await renderer.advanceFrames(1, 1);
  expect(facialWeights(renderer)).toEqual([0, 0, 0, 0, 0]);
  await act(async () => usePlaybackControlStore.getState().play());
  await renderer.advanceFrames(1, 3);
  expect(facialWeights(renderer)).toEqual(before);
});

it("keeps Classic turns immediate and enables facial motion when returning to Realistic", async () => {
  useSimulationStore.setState({ graphicsMode: "classic" });
  const renderer = await create(person(0)); renderers.push(renderer);
  await renderer.advanceFrames(1, 0);
  await renderer.update(person(1));
  await renderer.advanceFrames(1, 0.001);
  expect(renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y).toBe(1);
  expect(facialWeights(renderer)).toEqual([0, 0, 0, 0, 0]);
  await act(async () => useSimulationStore.setState({ graphicsMode: "realistic" }));
  await renderer.advanceFrames(1, 3);
  expect(facialWeights(renderer).some(weight => weight !== 0)).toBe(true);
});

it("closes the real morph completely, suppresses gaze, and holds the blink during pause", async () => {
  const phase = characterAnimationPhase("shopper-test:blink");
  let closure = 0;
  for (let i = 1000; i < 20000; i++) {
    if (shopperBlinkWeight(i / 1000, phase) === 1 && shopperBlinkWeight((i - 1) / 1000, phase) < 1) {
      closure = i / 1000;
      break;
    }
  }
  expect(closure).toBeGreaterThan(0);
  const renderer = await create(person(0)); renderers.push(renderer);
  await renderer.advanceFrames(1, closure);
  expect(facialWeights(renderer)).toEqual([1, 0, 0, 0, 0]);
  await act(async () => usePlaybackControlStore.getState().pause());
  await renderer.advanceFrames(1, 30);
  expect(facialWeights(renderer)).toEqual([1, 0, 0, 0, 0]);
  await act(async () => usePlaybackControlStore.getState().play());
  await renderer.advanceFrames(1, 0.25);
  expect(facialWeights(renderer)[0]).toBe(0);
  expect(facialWeights(renderer).slice(1).some(weight => weight > 0)).toBe(true);
});

it("keeps frame callbacks working after StrictMode's effect cleanup", async () => {
  const renderer = await create(<StrictMode>{person(0)}</StrictMode>); renderers.push(renderer);
  await renderer.advanceFrames(1, 0);
  await renderer.update(<StrictMode>{person(Math.PI / 2)}</StrictMode>);
  await renderer.advanceFrames(1, 0.5);
  expect(renderer.scene.findByProps({ name: "shopper-heading" }).instance.rotation.y).toBeCloseTo(Math.PI / 2 * (1 - Math.exp(-6)), 8);
  expect(facialWeights(renderer).some(weight => weight > 0)).toBe(true);
});
