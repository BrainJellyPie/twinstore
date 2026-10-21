// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Texture } from "three";
import { SimulationLayout } from "../SimulationLayout";
import { useSimulationStore } from "@/stores/simulationStore";
import type { StoreAssets } from "@/features/store-viewer/hooks/useStoreAssets";

vi.mock("@react-three/fiber", () => ({ useLoader: () => new Texture() }));
vi.mock("../SimulationCanvas", () => ({ SimulationCanvas: ({ currency }: { currency: string }) => <div data-testid="currency">{currency}</div> }));
vi.mock("@/features/playback/components/TimeBar", () => ({ TimeBar: () => null }));
vi.mock("@/features/dashboard/components/RackDetailPanel", () => ({ RackDetailPanel: () => null }));

afterEach(() => { cleanup(); useSimulationStore.getState().reset(); });

const assets: StoreAssets = { currency: "JPY", designTheme: "warm", width: 12, depth: 10, racks: [], doors: [], items: [],
  openHour: 9, closeHour: 21, minTime: 32400, maxTime: 75600, availableDays: [1] };

it.each(["ready", "running"] as const)("uses the selected layout currency in %s after viewing a different run", (mode) => {
  useSimulationStore.getState().setCurrency("KRW");
  render(<SimulationLayout storeId="test" assets={assets} personaNames={new Map()} personaGenders={new Map()}
    customers={null} heatmaps={null} mode={mode} />);
  expect(screen.getByTestId("currency").textContent).toBe("JPY");
  expect(useSimulationStore.getState().currency).toBe("JPY");
});

it("preserves a historical run's recorded currency during playback", () => {
  useSimulationStore.getState().setCurrency("KRW");
  render(<SimulationLayout storeId="test" assets={assets} personaNames={new Map()} personaGenders={new Map()}
    customers={[]} heatmaps={null} mode="playback" />);
  expect(screen.getByTestId("currency").textContent).toBe("KRW");
});
