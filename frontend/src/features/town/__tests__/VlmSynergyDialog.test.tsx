// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { VlmSynergyDialog } from "../VlmSynergyDialog";

vi.mock("@/shared/api/client", () => ({ startVlmSynergy: vi.fn(), getVlmSynergyJob: vi.fn() }));
vi.mock("@/features/runs/components/ModelPicker", () => ({ ModelPicker: () => null }));

const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); });

const venue: api.SynergyRow = { venue_id: "cafe", name: "Corner Cafe", category: "cafe", distance_m: 12,
  effect_on_focal_visitors: 10, effect_on_focal_pct: 0.1, role: "complement" };
const status: api.SynergyJobStatus = { job_id: "syn_test", venue_id: venue.venue_id, venue_name: venue.name,
  setup_id: "s1", status: "running", phase: "with venue", done: 3, total: 20, error: "", created_at: "", finished_at: "" };
const view = { status, result: null };

function show() {
  vi.mocked(api.startVlmSynergy).mockResolvedValue(status);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}>
    <VlmSynergyDialog projectId="p" venue={venue} dayType="weekday" scenarioId={null} onOpenChange={() => {}} />
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Run vision shoppers" }));
  return client;
}

it("shows that the first status is loading without starting another simulation", async () => {
  let resolve!: (value: typeof view) => void;
  vi.mocked(api.getVlmSynergyJob).mockReturnValue(new Promise((done) => { resolve = done; }));
  show();
  expect((await screen.findByRole("status")).textContent).toContain("Loading shopper status");
  await act(async () => resolve(view));
  expect(await screen.findByText("3 / 20 shopper visits")).toBeTruthy();
  expect(api.startVlmSynergy).toHaveBeenCalledOnce();
});

it("explains an initial status failure and retries the same job", async () => {
  vi.mocked(api.getVlmSynergyJob).mockRejectedValueOnce(new Error("Shopper status unavailable.")).mockResolvedValue(view);
  show();
  expect((await screen.findByRole("alert")).textContent).toContain("Shopper status unavailable.");
  fireEvent.click(screen.getByRole("button", { name: "Retry status" }));
  expect(await screen.findByText("3 / 20 shopper visits")).toBeTruthy();
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(api.startVlmSynergy).toHaveBeenCalledOnce();
  expect(api.getVlmSynergyJob).toHaveBeenLastCalledWith("p", "syn_test", expect.any(AbortSignal));
});

it("preserves progress after a polling failure and prevents repeat retries while fetching", async () => {
  vi.mocked(api.getVlmSynergyJob).mockResolvedValue(view);
  const client = show();
  await screen.findByText("3 / 20 shopper visits");
  vi.mocked(api.getVlmSynergyJob).mockRejectedValueOnce(new Error("Status connection lost."));
  await act(async () => { await client.invalidateQueries({ queryKey: ["projects", "p", "synergy-jobs", "syn_test"] }); });
  expect((await screen.findByRole("alert")).textContent).toContain("Status connection lost.");
  expect(screen.getByText("3 / 20 shopper visits")).toBeTruthy();
  let resolve!: (value: typeof view) => void;
  vi.mocked(api.getVlmSynergyJob).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  fireEvent.click(screen.getByRole("button", { name: "Retry status" }));
  const retry = screen.getByRole("button", { name: "Retry status" }) as HTMLButtonElement;
  await waitFor(() => expect(retry.disabled).toBe(true));
  fireEvent.click(retry);
  expect(api.getVlmSynergyJob).toHaveBeenCalledTimes(3);
  await act(async () => resolve({ ...view, status: { ...status, done: 9 } }));
  await screen.findByText("9 / 20 shopper visits");
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(api.startVlmSynergy).toHaveBeenCalledOnce();
});
