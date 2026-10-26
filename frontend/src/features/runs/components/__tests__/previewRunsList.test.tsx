// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { RunListItem } from "@/shared/api/client";
import { useSimulationStore } from "@/stores/simulationStore";
import { PreviewRunsList } from "../PreviewRunsList";

const runs = vi.hoisted(() => ({ list: [] as RunListItem[] }));
vi.mock("@/shared/queries/useRuns", () => ({ useRuns: () => ({ data: runs.list }) }));
afterEach(() => { cleanup(); document.querySelectorAll("[data-playback-play]").forEach((e) => e.remove()); });

it("names each run's View button after the run and hands focus to Play once the run shows", async () => {
  runs.list = [{ run_id: "r1", status: "completed", created_at: "2026-10-26T15:12:00", engine_type: "rule_based", seed: 0,
    summary: { conversion_rate: 0.91, revenue_per_visitor: 681, currency: "USD" } } as unknown as RunListItem];
  render(<PreviewRunsList projectId="p" setupId="s" />);
  const view = screen.getByRole("button", { name: /^View Rule-based · seed 0/ });
  fireEvent.click(view);
  expect(useSimulationStore.getState().viewRunId).toBe("r1");
  const play = Object.assign(document.createElement("button"), { textContent: "Play" });
  play.setAttribute("data-playback-play", "");
  setTimeout(() => document.body.append(play), 150);
  await waitFor(() => expect(document.activeElement).toBe(play), { timeout: 2000 });
});
