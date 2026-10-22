// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { OptimizeDialog } from "../OptimizeDialog";

vi.mock("@/shared/api/client", () => ({
  getScenarios: vi.fn(), startOptimization: vi.fn(), getOptimization: vi.fn(), readOptimizeGoal: vi.fn(),
  applyOptimization: vi.fn(), cancelOptimization: vi.fn(), getModels: vi.fn(),
}));
vi.mock("../../hooks", () => ({ useAvailableModels: () => ({ data: [], isError: false }) }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("sets the objective, scope, move limit and locked shelves from a goal, then starts with them", async () => {
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.readOptimizeGoal).mockResolvedValue({
    objective: "impulse_revenue", scope: "both", max_moves: 5, keep_fridges_on_walls: false, lock_rack_ids: ["r_till"],
    locked: ["Checkout"], min_improvement: 0.02, rationale: "Impulse sales with few changes.", warnings: ['No shelf "Moon shelf" in this layout; nothing was locked for it.'],
  });
  vi.mocked(api.startOptimization).mockImplementation(() => new Promise(() => {}));
  render(<QueryClientProvider client={new QueryClient()}><OptimizeDialog open onOpenChange={() => {}} projectId="p" setupId="s1" /></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Optimization goal"), { target: { value: "More impulse sales, keep the checkout, at most 5 changes" } });
  fireEvent.click(screen.getByRole("button", { name: "Set up" }));
  expect(await screen.findByText(/Impulse sales with few changes\./)).toBeTruthy();
  expect(api.readOptimizeGoal).toHaveBeenCalledWith("p", "s1", "More impulse sales, keep the checkout, at most 5 changes");
  expect(screen.getByText("Checkout")).toBeTruthy();
  expect(screen.getByText(/Moon shelf/)).toBeTruthy();
  fireEvent.click(screen.getAllByRole("button").find((b) => /^(Start|Optimize)/.test(b.textContent?.trim() ?? ""))!);
  await waitFor(() => expect(api.startOptimization).toHaveBeenCalled());
  const spec = vi.mocked(api.startOptimization).mock.calls[0]![2];
  expect(spec).toMatchObject({ objective: "impulse_revenue", scope: "both",
    constraints: { max_moves: 5, keep_fridges_on_walls: false, lock_rack_ids: ["r_till"], min_improvement: 0.02 } });
});

it("reads a goal routed from the command palette once", async () => {
  vi.mocked(api.getScenarios).mockResolvedValue([]);
  vi.mocked(api.readOptimizeGoal).mockResolvedValue({ objective: "conversion_rate", scope: "planogram", max_moves: null,
    keep_fridges_on_walls: null, lock_rack_ids: [], locked: [], min_improvement: null, rationale: "Conversion first.", warnings: [] });
  render(<QueryClientProvider client={new QueryClient()}>
    <OptimizeDialog open onOpenChange={() => {}} projectId="p" setupId="s1" goalPrefill={{ id: 3, text: "Get more visitors to buy" }} />
  </QueryClientProvider>);
  expect(await screen.findByText(/Conversion first\./)).toBeTruthy();
  expect(api.readOptimizeGoal).toHaveBeenCalledTimes(1);
  expect((screen.getByLabelText("Optimization goal") as HTMLInputElement).value).toBe("Get more visitors to buy");
});
