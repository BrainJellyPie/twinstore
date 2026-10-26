// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { getJourney } from "@/shared/api/interview";
import type { CustomerResult, Persona, Store } from "@/shared/types/domain";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { ShopperPanel } from "../ShopperPanel";

vi.mock("@/shared/api/interview", async (original) => ({
  ...await original<typeof import("@/shared/api/interview")>(), getJourney: vi.fn(),
}));
afterEach(() => { cleanup(); vi.clearAllMocks(); useSimulationStore.getState().setFollowPersonaId(null); });

const customers = [
  { persona_id: "p1", day: 2, arrival_time: "15:30:00", leave_time: "15:40:00", total_spent: 0, timeline: [] },
  { persona_id: "p2", day: 1, arrival_time: "09:00:00", leave_time: "09:10:00", total_spent: 500, timeline: [] },
] as unknown as CustomerResult[];
const personas = [{ id: "p1", identity: "Student", age_group: "20s", gender: "Female" }, { id: "p2", identity: "Nurse", age_group: "30s", gender: "Male" }] as unknown as Persona[];

it("follows a shopper in 3D straight from the list, from their arrival", () => {
  vi.mocked(getJourney).mockImplementation(() => new Promise(() => {}));
  const seek = vi.spyOn(usePlaybackControlStore.getState(), "seek");
  render(<QueryClientProvider client={new QueryClient()}>
    <ShopperPanel projectId="p" runId="r" customers={customers} personas={personas} store={{ racks: [] } as unknown as Store} />
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Follow Student in 3D" }));
  expect(useSimulationStore.getState().followPersonaId).toBe("p1");
  expect(useSimulationStore.getState().highlightId).toBe("p1");
  expect(usePlaybackControlStore.getState().currentDay).toBe(2);
  expect(seek).toHaveBeenCalledWith(15.5 * 3600);
  // The shopper's journey opens beside the 3D view.
  expect(screen.getByRole("button", { name: "All shoppers" })).toBeTruthy();
});

it("opens the first shopper a search finds with Enter and moves into the list with the down arrow", () => {
  vi.mocked(getJourney).mockImplementation(() => new Promise(() => {}));
  render(<QueryClientProvider client={new QueryClient()}>
    <ShopperPanel projectId="p" runId="r" customers={customers} personas={personas} store={{ racks: [] } as unknown as Store} />
  </QueryClientProvider>);
  const box = screen.getByRole("textbox", { name: "Search 2 shoppers" });
  fireEvent.change(box, { target: { value: "nurse" } });
  fireEvent.keyDown(box, { key: "ArrowDown" });
  expect(document.activeElement?.textContent).toContain("Nurse");
  fireEvent.keyDown(box, { key: "Enter", isComposing: true });
  expect(screen.queryByRole("button", { name: "All shoppers" })).toBeNull();
  fireEvent.keyDown(box, { key: "Enter" });
  expect(screen.getByRole("button", { name: "All shoppers" })).toBeTruthy();
  expect(useSimulationStore.getState().highlightId).toBe("p2");
});
