// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { SimulationCanvas, type SimulationCanvasProps } from "../SimulationCanvas";
import { usePhotoMode } from "@/features/store-viewer/realistic/photoModeStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { useLocale } from "@/shared/i18n/i18n";

// Exercise canvas ownership and real DOM events without a GPU or a Three scene.
vi.mock("@react-three/fiber", async (original) => {
  const { useEffect, useRef } = await import("react");
  return { ...await original<typeof import("@react-three/fiber")>(), Canvas: function Canvas({ onCreated }: {
    onCreated: (state: { gl: { debug: { checkShaderErrors: boolean }; domElement: HTMLCanvasElement } }) => void;
  }) {
    const element = useRef<HTMLCanvasElement>(null);
    const create = useRef(onCreated);
    useEffect(() => {
      create.current({ gl: { debug: { checkShaderErrors: false }, domElement: element.current! } });
    }, []);
    return <canvas ref={element} data-testid="store-canvas" />;
  } };
});
vi.mock("@react-three/drei", async (original) => ({ ...await original<typeof import("@react-three/drei")>(),
  useGLTF: Object.assign(vi.fn(), { preload: vi.fn() }),
}));
vi.mock("@/features/store-viewer/realistic/RealisticHud", () => ({ RealisticHud: () => null }));

const props: SimulationCanvasProps = {
  width: 4, depth: 4, racks: [], doors: [], items: [], heatmapData: null, heatmapPalette: null,
  rackStats: null, currency: "USD", customers: null, personaNames: new Map(), personaGenders: new Map(),
  minTime: 0, maxTime: 3600, availableDays: [1], variationTexture: null,
};
beforeEach(() => { useLocale.getState().setLocale("en"); useSimulationStore.getState().reset(); usePhotoMode.getState().stop(); });
afterEach(() => { cleanup(); usePhotoMode.getState().stop(); });
const event = (canvas: HTMLElement, type: "webglcontextlost" | "webglcontextrestored") => {
  act(() => { canvas.dispatchEvent(new Event(type, { cancelable: true })); });
};

it("stops Photo mode on active context loss and clears the message on restoration", () => {
  render(<SimulationCanvas {...props} />);
  usePhotoMode.getState().start();
  const canvas = screen.getByTestId("store-canvas");
  event(canvas, "webglcontextlost");
  expect(usePhotoMode.getState().status).toBe("off");
  expect(screen.getByRole("alert")).toBeTruthy();
  event(canvas, "webglcontextrestored");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("ignores delayed loss/restoration from the replaced canvas while keeping the new canvas active", () => {
  render(<SimulationCanvas {...props} />);
  const old = screen.getByTestId("store-canvas");
  event(old, "webglcontextlost");
  fireEvent.click(screen.getByRole("button", { name: "Restart the 3D view" }));
  const current = screen.getByTestId("store-canvas");
  expect(current).not.toBe(old);
  usePhotoMode.getState().start();
  // R3F disposes an old renderer later and calls forceContextLoss on it.
  event(old, "webglcontextlost");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(usePhotoMode.getState().status).toBe("building");
  event(current, "webglcontextlost");
  event(old, "webglcontextrestored");
  expect(screen.getByRole("alert")).toBeTruthy();
  event(current, "webglcontextrestored");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("detaches listeners when leaving the store so disposal cannot stop a later Photo session", () => {
  const view = render(<SimulationCanvas {...props} />);
  const old = screen.getByTestId("store-canvas");
  view.unmount();
  usePhotoMode.getState().start();
  event(old, "webglcontextlost");
  expect(usePhotoMode.getState().status).toBe("building");
});

it("keeps context listeners working after Strict Mode replays effects", () => {
  render(<StrictMode><SimulationCanvas {...props} /></StrictMode>);
  const canvas = screen.getByTestId("store-canvas");
  event(canvas, "webglcontextlost");
  expect(screen.getByRole("alert")).toBeTruthy();
  event(canvas, "webglcontextrestored");
  expect(screen.queryByRole("alert")).toBeNull();
});
