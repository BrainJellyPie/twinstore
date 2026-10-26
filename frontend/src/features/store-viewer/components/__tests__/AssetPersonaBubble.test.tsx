import { useMemo, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { create, act } from "@react-three/test-renderer";
import { AssetPersona } from "../AssetPersona";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import type { TimelineEvent } from "@/shared/types/domain";

const html = vi.hoisted(() => ({ rendered: [] as string[] }));
// Html overlays are DOM, outside the test scene: record what they would show.
vi.mock("@react-three/drei", async () => ({
  ...await import("@react-three/drei/core/useAnimations.js"),
  Html: ({ children }: { children: ReactNode }) => { html.rendered.push(renderToStaticMarkup(<>{children}</>)); return null; },
}));
vi.mock("@/shared/hooks/useGlbModel", () => ({
  useGlbModel: () => {
    const clone = useMemo(() => new THREE.Group(), []);
    return { clone, bbox: { size: new THREE.Vector3(0.4, 1.8, 0.3) }, offset: new THREE.Vector3(), animations: [] };
  },
}));
const originalWarn = console.warn;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.spyOn(console, "warn").mockImplementation((message, ...args) => {
    if (message !== "THREE.THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.") originalWarn(message, ...args);
  });
});
afterEach(() => { html.rendered = []; useSimulationMetricsStore.getState().reset(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const walk: TimelineEvent = { elapsed_sec: 1, x: 0, y: 0, action: "move", duration: 0, target_rack: "", face: null,
  description: "Walks directly to the fridge.", product_sku: "", product_name: "", price: 0 };

it("drops a shopper's speech bubble once the day shows Closed", async () => {
  const renderer = await create(<AssetPersona personaId="p1" gender="Female" facing={0} isMoving color="#ddd" label="Student" event={walk} />);
  expect(html.rendered.some((markup) => markup.includes("Walks directly to the fridge."))).toBe(true);
  html.rendered = [];
  await act(async () => useSimulationMetricsStore.getState().setMetrics({ finished: true }));
  expect(html.rendered.some((markup) => markup.includes("Student"))).toBe(true);
  expect(html.rendered.some((markup) => markup.includes("Walks directly to the fridge."))).toBe(false);
  await renderer.unmount();
});

it("wraps a long thought or checkout description but keeps a purchase on one line", async () => {
  const pay: TimelineEvent = { ...walk, action: "pay", description: "Places the pistachios, beef jerky, KIND bars and gelato on the counter." };
  const buy: TimelineEvent = { ...walk, action: "buy", product_name: "Cherry Coke 20oz", price: 199 };
  for (const [event, wraps] of [[walk, true], [pay, true], [buy, false]] as const) {
    html.rendered = [];
    const renderer = await create(<AssetPersona personaId="p1" gender="Female" facing={0} isMoving color="#ddd" label="Student" event={event} />);
    const bubble = html.rendered.find((markup) => markup.includes(event.product_name || event.description))!;
    expect(bubble.includes("white-space:nowrap")).toBe(!wraps);
    expect(bubble.includes("-webkit-line-clamp:3")).toBe(wraps);
    await renderer.unmount();
  }
});
