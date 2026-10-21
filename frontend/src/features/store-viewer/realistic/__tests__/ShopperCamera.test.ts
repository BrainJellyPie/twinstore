// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactElement, RefObject } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { ShopperCamera } from "../ShopperCamera";
import { livePlaybackClock } from "../playbackClock";
import { personaRegistry } from "../personaRegistry";

const context = vi.hoisted(() => ({ frame: null as ((state: unknown, delta: number) => void) | null }));
vi.mock("@react-three/fiber", () => ({ useFrame: (callback: typeof context.frame) => { context.frame = callback; } }));
vi.mock("@react-three/drei", () => ({ PerspectiveCamera: () => null }));
const ev = (elapsed_sec: number, x: number, action: string, duration = 0): TimelineEvent => ({
  elapsed_sec, x, y: 2, action, duration, target_rack: "shelf", face: "S", description: "",
  product_sku: "", product_name: "", price: 0,
});
const customer: CustomerResult = { persona_id: "follow", day: 1, arrival_time: "08:00:00", leave_time: "", total_spent: 0,
  timeline: [ev(0, 0, "enter"), ev(2, 1, "browse", 10), ev(15, 2, "move"), ev(20, 3, "exit")] };
const options = { active: true, customers: [customer], racks: [], width: 4, depth: 5, minTime: 28800, maxTime: 28920, eyeHeight: 1.24 };
const tick = (delta = 0.1) => act(() => { context.frame!({}, delta); });
function mount(customers = [customer]) {
  const hook = renderHook(() => ShopperCamera({ ...options, customers }));
  const element = hook.result.current as ReactElement<{ ref: RefObject<THREE.PerspectiveCamera | null> }>;
  const camera = new THREE.PerspectiveCamera();
  element.props.ref.current = camera;
  return camera;
}
beforeEach(() => {
  usePlaybackControlStore.getState().reset();
  useSimulationMetricsStore.getState().reset();
  useSimulationMetricsStore.getState().setCurrentMinute(28800);
  useSimulationStore.getState().reset();
  useSimulationStore.setState({ followPersonaId: "follow" });
  personaRegistry.count = 0;
  personaRegistry.hideNear = null;
  livePlaybackClock.current = { time: { current: 28807 }, day: { current: 1 } };
});
afterEach(() => { cleanup(); livePlaybackClock.current = null; personaRegistry.count = 0; personaRegistry.hideNear = null; });

it.each(([1, 60, 600, 3600] as const).flatMap(speed => [1 / 120, 0.1, 0.5, 2].map(delta => ({ speed, delta }))))(
  "uses exact playback time with speed $speed and frame interval $delta", ({ speed, delta }) => {
    usePlaybackControlStore.getState().setSpeed(speed);
    usePlaybackControlStore.getState().play();
    const camera = mount();
    for (let i = 0; i < 12; i++) tick(delta);
    expect(personaRegistry.hideNear).toEqual({ x: 1.5, z: 2.5 });
    expect(camera.position.x).toBeCloseTo(-0.5);
    const direction = camera.getWorldDirection(new THREE.Vector3());
    expect(direction.z).toBeLessThan(-0.95);
    expect(Math.abs(direction.x)).toBeLessThan(1e-6);
  },
);

it("updates the selected pose between selector-list refreshes", () => {
  livePlaybackClock.current!.time.current = 28801;
  mount(); tick();
  expect(personaRegistry.hideNear!.x).toBe(1);
  livePlaybackClock.current!.time.current = 28801.5;
  tick();
  expect(personaRegistry.hideNear!.x).toBe(1.25);
  livePlaybackClock.current!.time.current = 28807;
  tick();
  expect(personaRegistry.hideNear!.x).toBe(1.5);
});

it("does not snap the selected shopper's camera to an unrelated nearby body", () => {
  personaRegistry.count = 1;
  personaRegistry.xs[0] = 1.7;
  personaRegistry.zs[0] = 2.6;
  const camera = mount(); tick();
  expect(personaRegistry.hideNear).toEqual({ x: 1.5, z: 2.5 });
  expect(camera.position.x).toBeCloseTo(-0.5);
});

it("changes to an active shopper immediately when the selected shopper exits", () => {
  const second = { ...customer, persona_id: "second", arrival_time: "08:00:10", timeline: [ev(0, 3, "enter"), ev(100, 3, "exit")] };
  mount([customer, second]); tick();
  livePlaybackClock.current!.time.current = 28820;
  tick();
  expect(personaRegistry.hideNear!.x).toBe(3.5);
});

it("handles a day change and a backward seek without following the previous day", () => {
  const nextDay = { ...customer, day: 5, timeline: [ev(0, 3, "enter"), ev(100, 3, "exit")] };
  mount([customer, nextDay]); tick();
  usePlaybackControlStore.getState().setDay(5);
  livePlaybackClock.current!.day.current = 5;
  tick();
  expect(personaRegistry.hideNear!.x).toBe(3.5);
  usePlaybackControlStore.getState().setDay(1);
  livePlaybackClock.current!.day.current = 1;
  livePlaybackClock.current!.time.current = 28801;
  tick();
  expect(personaRegistry.hideNear!.x).toBe(1);
});

it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])("falls back safely for a non-finite clock %s", time => {
  livePlaybackClock.current!.time.current = time;
  const camera = mount(); tick();
  expect(camera.position.toArray().every(Number.isFinite)).toBe(true);
  expect(personaRegistry.hideNear!.x).toBe(0.5);
});

it("ignores a clock owned by another day", () => {
  livePlaybackClock.current!.day.current = 5;
  mount(); tick();
  expect(personaRegistry.hideNear!.x).toBe(0.5);
});

it("uses wall-clock delta for standalone previews without a playback loop", () => {
  livePlaybackClock.current = null;
  usePlaybackControlStore.getState().setSpeed(1);
  usePlaybackControlStore.getState().play();
  mount(); tick(0.5); tick(0.5);
  expect(personaRegistry.hideNear!.x).toBe(0.75);
});
