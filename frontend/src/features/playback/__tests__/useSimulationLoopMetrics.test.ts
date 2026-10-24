// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { CustomerResult, Store, TimelineEvent } from "@/shared/types/domain";
import { useStoreAssets } from "@/features/store-viewer/hooks/useStoreAssets";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationLoop } from "../hooks/useSimulationLoop";

const context = vi.hoisted(() => ({ frame: null as ((state: unknown, delta: number) => void) | null }));
vi.mock("@react-three/fiber", () => ({ useFrame: (callback: typeof context.frame) => { context.frame = callback; } }));
const event = (elapsed_sec: number, action: string, extra: Partial<TimelineEvent> = {}): TimelineEvent => ({
  elapsed_sec, action, x: 0, y: 0, duration: 0, target_rack: "rack", face: null,
  description: "", product_sku: "", product_name: "", price: 0, ...extra,
});
const customers: CustomerResult[] = [1, 2, 3].map(day => ({
  persona_id: `p${day}`, day, arrival_time: "10:00:00", leave_time: "", total_spent: day * 100,
  timeline: [event(0, "enter"), event(1, "buy", { product_sku: "same", product_name: "Same", price: 100, quantity: day }),
    event(2, "pay"), event(3, "exit")],
}));
const options = { customers, personaNames: new Map<string, string>(), personaGenders: new Map<string, string>(),
  minTime: 36000, maxTime: 36030, availableDays: [1, 2, 3] };
const tick = (delta = 0) => act(() => { context.frame!({}, delta); });
const assertSales = (quantity: number) => {
  const metrics = useSimulationMetricsStore.getState();
  expect(metrics.revenue).toBe(quantity * 100);
  expect(metrics.skuSales).toEqual([expect.objectContaining({ sku: "same", quantity, revenue: quantity * 100 })]);
};
beforeEach(() => { usePlaybackControlStore.getState().reset(); useSimulationMetricsStore.getState().reset(); });
afterEach(cleanup);

it("restores prior sales on a day change and repeated backward seeks", () => {
  renderHook(() => useSimulationLoop(options));
  usePlaybackControlStore.getState().setDay(2);
  tick(); tick();
  assertSales(1);
  for (const [seconds, quantity] of [[5, 3], [0, 1], [5, 3]] as const) {
    usePlaybackControlStore.getState().seek(36000 + seconds);
    tick(); tick();
    assertSales(quantity);
  }
});

it("carries only completed days into automatic day transitions", () => {
  renderHook(() => useSimulationLoop(options));
  usePlaybackControlStore.getState().play();
  tick(30 / 60);
  expect(usePlaybackControlStore.getState().currentDay).toBe(2);
  assertSales(1);
  tick(5 / 60);
  assertSales(3);
  tick(25 / 60);
  expect(usePlaybackControlStore.getState().currentDay).toBe(3);
  assertSales(3);
});

it("plays the final day's purchase and departure after midnight before finishing", () => {
  const store: Store = { id: "night", name: "Late shop", type: "shop", grid_size: [5, 5], racks: [],
    weekly_schedule: [{ day: 1, is_open: true, open_hour: 23, close_hour: 24 }] };
  const late: CustomerResult = { ...customers[0]!, arrival_time: "23:59:00", timeline: [
    event(0, "enter"), event(90, "buy", { product_sku: "same", product_name: "Same", price: 100, quantity: 1 }),
    event(120, "pay"), event(180, "exit", { duration: 10 }),
  ] };
  const people = [late];
  renderHook(() => {
    const assets = useStoreAssets(store, people);
    return useSimulationLoop({ ...options, ...assets, customers: people });
  });
  usePlaybackControlStore.getState().play();
  tick(61);
  assertSales(1);
  expect(useSimulationMetricsStore.getState()).toMatchObject({ finished: false, inStore: 1 });
  tick(70 / 60);
  expect(useSimulationMetricsStore.getState()).toMatchObject({ finished: true, inStore: 0, revenue: 100 });
});

it.each([{ availableDays: [1] }, { availableDays: [2, 5] }])("can play and finish an empty result for weekdays $availableDays", ({ availableDays }) => {
  usePlaybackControlStore.getState().setAvailableDays(availableDays);
  const hook = renderHook(() => useSimulationLoop({ ...options, customers: [], availableDays }));
  usePlaybackControlStore.getState().play();
  tick(5 / 60);
  expect(hook.result.current.playbackTimeRef.current).toBe(36005);
  for (let i = 0; i < availableDays.length; i++) tick(30 / 60);
  expect(usePlaybackControlStore.getState()).toMatchObject({ playing: false, currentDay: availableDays[availableDays.length - 1] });
  expect(useSimulationMetricsStore.getState()).toMatchObject({ finished: true, revenue: 0, inStore: 0 });
  expect(hook.result.current.personaFramesRef.current).toEqual([]);
});

it.each([{ availableDays: [1] }, { availableDays: [2, 5] }])("can skip and reset an empty result for weekdays $availableDays", ({ availableDays }) => {
  usePlaybackControlStore.getState().setAvailableDays(availableDays);
  const hook = renderHook(() => useSimulationLoop({ ...options, customers: [], availableDays }));
  usePlaybackControlStore.getState().seek(options.maxTime);
  tick();
  expect(useSimulationMetricsStore.getState()).toMatchObject({ finished: true, revenue: 0 });
  expect(hook.result.current.playbackTimeRef.current).toBe(options.maxTime);
  usePlaybackControlStore.getState().setDay(availableDays[0]!);
  usePlaybackControlStore.getState().seek(options.minTime);
  tick(); tick();
  expect(hook.result.current.playbackTimeRef.current).toBe(options.minTime);
  expect(useSimulationMetricsStore.getState()).toMatchObject({ finished: false, revenue: 0 });
  expect(usePlaybackControlStore.getState().seekTarget).toBeNull();
});
