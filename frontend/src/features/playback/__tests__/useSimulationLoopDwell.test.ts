// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { CustomerResult, TimelineEvent } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { shopperPoseAt } from "@/features/store-viewer/realistic/shopperPose";
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
