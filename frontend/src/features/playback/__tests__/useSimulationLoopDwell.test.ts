// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { shopperPoseAt } from "@/features/store-viewer/realistic/shopperPose";
import { livePlaybackClock } from "@/features/store-viewer/realistic/playbackClock";
import { useSimulationLoop } from "../hooks/useSimulationLoop";

const context = vi.hoisted(() => ({ frame: null as ((state: unknown, delta: number) => void) | null }));
vi.mock("@react-three/fiber", () => ({ useFrame: (callback: typeof context.frame) => { context.frame = callback; } }));
const ev = (elapsed_sec: number, x: number, action: string, extra: Partial<TimelineEvent> = {}): TimelineEvent => ({
  elapsed_sec, x, y: 2, action, duration: 0, target_rack: "shelf", face: "S", description: "",
  product_sku: "", product_name: "", price: 0, ...extra,
});
const shopper: CustomerResult = {
  persona_id: "customer", day: 1, arrival_time: "08:00:00", leave_time: "", total_spent: 100,
  timeline: [ev(0, 0, "enter"), ev(2, 1, "browse", { duration: 10 }), ev(15, 2, "move"),
    ev(16, 2, "buy", { duration: 1, price: 100, product_sku: "lemon" }), ev(18, 2, "pay"), ev(20, 3, "exit")],
};
const options = { customers: [shopper], personaNames: new Map([["customer", "Customer"]]),
  personaGenders: new Map([["customer", "Female"]]), minTime: 28800, maxTime: 28830, availableDays: [1] };
const tick = (delta = 0) => act(() => { context.frame!({}, delta); });
const seek = (seconds: number) => { usePlaybackControlStore.getState().seek(28800 + seconds); tick(); tick(); };
beforeEach(() => { usePlaybackControlStore.getState().reset(); useSimulationMetricsStore.getState().reset(); });
afterEach(cleanup);

it.each([false, true])("orders the till line by clock time across different arrival times (left=%s)", left => {
  const early: CustomerResult = { ...shopper, persona_id: "early", queue_wait_sec: 300, left_queue: left,
    timeline: [ev(0, 4, "enter"), ev(600, left ? 4 : 1, "wander", { duration: 300 }),
      ...(left ? [] : [ev(900, 4, "pay", { duration: 10 })]), ev(920, 5, "exit")] };
  const later: CustomerResult = { ...shopper, persona_id: "later", arrival_time: "08:09:00", queue_wait_sec: 280,
    timeline: [ev(0, 4, "enter"), ev(120, 2, "wander", { duration: 280 }),
      ev(400, 4, "pay", { duration: 10 }), ev(420, 5, "exit")] };
  const hook = renderHook(() => useSimulationLoop({ ...options, customers: [later, early], maxTime: 30000,
    counters: [{ x: 4, y: 1 }] }));
  for (const seconds of [730, 800, 730]) {
    seek(seconds);
    const frames = new Map(hook.result.current.personaFramesRef.current.map(frame => [frame.id, frame]));
    expect(frames.get("early")!.y).toBeCloseTo(2.55);
    expect(frames.get("later")!.y).toBeCloseTo(3.1);
    expect(frames.get("early")!.x).toBe(4);
    expect(frames.get("later")!.x).toBe(4);
    expect(frames.get("early")!.isMoving).toBe(false);
    expect(frames.get("later")!.isMoving).toBe(false);
  }
});

it.each([2, 7, 11.999, 12, 13.5, 15, 16, 16.999, 18.5])("keeps rendered body and camera at the same pose at %ss", seconds => {
  const hook = renderHook(() => useSimulationLoop(options));
  seek(seconds);
  const body = hook.result.current.personaFramesRef.current[0]!;
  const camera = shopperPoseAt(shopper, 28800 + seconds)!;
  expect(body.x + 0.5).toBeCloseTo(camera.x, 8);
  expect(body.y + 0.5).toBeCloseTo(camera.z, 8);
  expect(body.facing).toBeCloseTo(camera.lookYaw, 8);
  expect(body.isMoving).toBe(camera.moving);
  if (seconds < 12 || seconds >= 16 && seconds < 17) expect(body.isMoving).toBe(false);
  if (seconds >= 2 && seconds < 12) {
    expect(body.x).toBe(1);
    expect(body.currentEvent?.action).toBe("browse");
  }
});

it("freezes a paused dwell and resumes movement only after its end", () => {
  const hook = renderHook(() => useSimulationLoop(options));
  seek(11.5);
  tick(10);
  expect(hook.result.current.playbackTimeRef.current).toBe(28811.5);
  expect(hook.result.current.personaFramesRef.current[0]!.isMoving).toBe(false);
  usePlaybackControlStore.getState().play();
  tick(0.5 / 60);
  expect(hook.result.current.personaFramesRef.current[0]!).toMatchObject({ x: 1, isMoving: true });
  tick(1.5 / 60);
  expect(hook.result.current.personaFramesRef.current[0]!.x).toBeCloseTo(1.5);
});

it("rebuilds a dwell after backward seeking without duplicating purchases", () => {
  const hook = renderHook(() => useSimulationLoop(options));
  seek(19);
  expect(useSimulationMetricsStore.getState().revenue).toBe(100);
  seek(7);
  expect(hook.result.current.personaFramesRef.current[0]!).toMatchObject({ x: 1, isMoving: false });
  expect(useSimulationMetricsStore.getState().revenue).toBe(0);
  seek(19);
  expect(useSimulationMetricsStore.getState().revenue).toBe(100);
  seek(20);
  expect(hook.result.current.personaFramesRef.current).toHaveLength(0);
});

it.each([1 / 120, 1 / 60, 0.1, 0.25, 1])("advances one simulation second per wall second at real time (delta=%s)", delta => {
  const hook = renderHook(() => useSimulationLoop(options));
  seek(11.5);
  usePlaybackControlStore.getState().setSpeed(1);
  usePlaybackControlStore.getState().play();
  for (let i = 0; i < Math.round(1 / delta); i++) tick(delta);
  expect(hook.result.current.playbackTimeRef.current).toBeCloseTo(28812.5, 6);
  expect(hook.result.current.personaFramesRef.current[0]!.x).toBeCloseTo(1 + 0.5 / 3, 6);
  usePlaybackControlStore.getState().pause();
  tick(5);
  expect(hook.result.current.playbackTimeRef.current).toBeCloseTo(28812.5, 6);
});

it("changes between real time and accelerated playback without restarting the stop", () => {
  const hook = renderHook(() => useSimulationLoop(options));
  seek(2);
  usePlaybackControlStore.getState().setSpeed(1);
  usePlaybackControlStore.getState().play();
  tick(3);
  usePlaybackControlStore.getState().setSpeed(60);
  tick(0.1);
  expect(hook.result.current.playbackTimeRef.current).toBe(28811);
  expect(hook.result.current.personaFramesRef.current[0]!.isMoving).toBe(false);
  usePlaybackControlStore.getState().setSpeed(1);
  tick(1);
  expect(hook.result.current.personaFramesRef.current[0]!).toMatchObject({ x: 1, isMoving: true });
});

it("ends at closing time and pauses real-time playback", () => {
  const hook = renderHook(() => useSimulationLoop(options));
  seek(29.5);
  usePlaybackControlStore.getState().setSpeed(1);
  usePlaybackControlStore.getState().play();
  tick(1);
  expect(hook.result.current.playbackTimeRef.current).toBe(28830);
  expect(usePlaybackControlStore.getState()).toMatchObject({ speed: 1, playing: false });
  expect(useSimulationMetricsStore.getState().finished).toBe(true);
  expect(hook.result.current.personaFramesRef.current).toHaveLength(0);
  tick(10);
  expect(hook.result.current.playbackTimeRef.current).toBe(28830);
});

it("continues at real time when a sparse schedule advances to its next open day", () => {
  const days = [2, 5];
  usePlaybackControlStore.getState().setAvailableDays(days);
  const multi = { ...options, availableDays: days, customers: days.map(day => ({ ...shopper, day })) };
  const hook = renderHook(() => useSimulationLoop(multi));
  seek(29.5);
  usePlaybackControlStore.getState().setSpeed(1);
  usePlaybackControlStore.getState().play();
  tick(1);
  expect(usePlaybackControlStore.getState()).toMatchObject({ currentDay: 5, speed: 1, playing: true });
  expect(hook.result.current.playbackTimeRef.current).toBe(28800);
  tick(0.5);
  expect(hook.result.current.playbackTimeRef.current).toBe(28800.5);
  expect(useSimulationMetricsStore.getState().finished).toBe(false);
});

it("publishes its exact time ref without notifying React subscribers each frame", () => {
  const hook = renderHook(() => useSimulationLoop(options));
  const source = livePlaybackClock.current!;
  expect(source.time).toBe(hook.result.current.playbackTimeRef);
  seek(7);
  expect(source.time.current).toBe(28807);
  usePlaybackControlStore.getState().setSpeed(1);
  usePlaybackControlStore.getState().play();
  const subscriber = vi.fn();
  const unsubscribe = useSimulationMetricsStore.subscribe(subscriber);
  tick(0.5);
  unsubscribe();
  expect(source.time.current).toBe(28807.5);
  expect(subscriber).not.toHaveBeenCalled();
  usePlaybackControlStore.getState().pause();
  tick(10);
  expect(source.time.current).toBe(28807.5);
  seek(2);
  expect(source.time.current).toBe(28802);
  hook.unmount();
  expect(livePlaybackClock.current).toBeNull();
});

it("rebinds the clock after StrictMode effect replay and releases it on unmount", () => {
  const hook = renderHook(() => useSimulationLoop(options), { wrapper: StrictMode });
  expect(livePlaybackClock.current!.time).toBe(hook.result.current.playbackTimeRef);
  seek(7);
  expect(livePlaybackClock.current!.time.current).toBe(28807);
  hook.unmount();
  expect(livePlaybackClock.current).toBeNull();
});

it("does not clear a replacement loop's clock when the old loop unmounts", () => {
  const previous = renderHook(() => useSimulationLoop(options));
  const replacement = renderHook(() => useSimulationLoop({ ...options, minTime: 28801 }));
  previous.unmount();
  expect(livePlaybackClock.current!.time).toBe(replacement.result.current.playbackTimeRef);
  expect(livePlaybackClock.current!.time.current).toBe(28801);
  replacement.unmount();
  expect(livePlaybackClock.current).toBeNull();
});
