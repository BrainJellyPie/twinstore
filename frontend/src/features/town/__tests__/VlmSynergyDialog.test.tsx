// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { VlmSynergyDialog } from "../VlmSynergyDialog";
import { useSimulationStore } from "@/stores/simulationStore";

vi.mock("@/shared/api/client", () => ({ startVlmSynergy: vi.fn(), getVlmSynergyJob: vi.fn() }));
vi.mock("@/features/runs/components/ModelPicker", () => ({ ModelPicker: () => null }));

const clients: QueryClient[] = [];
afterEach(() => { cleanup(); clients.splice(0).forEach((client) => client.clear()); vi.resetAllMocks(); useSimulationStore.getState().reset(); });

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

function completed(currency?: string | null): { status: api.SynergyJobStatus; result: api.VLMSynergyResult & { currency?: string | null } } {
  return { status: { ...status, status: "completed", phase: "done", done: 20 }, result: {
    currency, venue_id: venue.venue_id, venue_name: venue.name, category: "cafe", distance_m: 12, model: "offline fixture",
    visitors_with: 20, visitors_without: 10, delta_visitors: 10, linked_visitors_from_venue: 10, panel_customers: 4,
    affected_customers: 2, affected_share: 0.5, spend_per_visitor_with: 1500, spend_per_visitor_without: 1000,
    delta_spend_per_visitor: 500, delta_spend_ci_low: -200, delta_spend_ci_high: 800, prob_spend_higher: 0.8,
    conversion_with: 0.5, conversion_without: 0.25, delta_conversion: 0.25, category_shifts: [],
    revenue_per_day_with: 2000, revenue_per_day_without: 1000, delta_revenue_per_day: 1000,
    delta_revenue_from_visitors: 300, delta_revenue_from_baskets: 700, examples: [], vlm_requests: 0,
    failed_customers: 0, seconds: 0, notes: [],
  } };
}
const monetaryCases = [
  ["USD", "$10.00"], ["KRW", "₩1,000"], ["JPY", "¥1,000"], ["EUR", "€10.00"], ["USD_CENTS", "$10.00"],
].flatMap(([currency, expected]) => ["USD", "KRW"].map(previousCurrency => ({ currency, expected, previousCurrency })));
it.each(monetaryCases)("uses saved $currency amounts after viewing a $previousCurrency simulation", async ({ currency, expected, previousCurrency }) => {
  useSimulationStore.getState().setCurrency(previousCurrency!);
  vi.mocked(api.getVlmSynergyJob).mockResolvedValue(completed(currency)); show();
  expect(await screen.findByText(`+${expected} / day`)).toBeTruthy(); expect(api.startVlmSynergy).toHaveBeenCalledOnce();
});
it.each([undefined, null, ""])("keeps legacy results without currency (%s) in unconverted minor units", async currency => {
  useSimulationStore.getState().setCurrency("USD"); vi.mocked(api.getVlmSynergyJob).mockResolvedValue(completed(currency)); show();
  expect(await screen.findByText("+1,000 minor units / day")).toBeTruthy();
  expect(screen.getByText("Currency was not recorded for this saved result. Amounts are shown in minor units.")).toBeTruthy();
  expect(screen.queryByText(/\$/)).toBeNull(); expect(api.startVlmSynergy).toHaveBeenCalledOnce();
});
it("keeps a displayed result in its own currency when another simulation changes the global currency", async () => {
  useSimulationStore.getState().setCurrency("KRW"); vi.mocked(api.getVlmSynergyJob).mockResolvedValue(completed("KRW")); show();
  await screen.findByText("+₩1,000 / day"); act(() => useSimulationStore.getState().setCurrency("USD"));
  expect(screen.getByText("+₩1,000 / day")).toBeTruthy(); expect(screen.queryByText("+$10.00 / day")).toBeNull();
});

it("says how many vision-shopper visits a run takes before it starts", () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); clients.push(client);
  render(<QueryClientProvider client={client}>
    <VlmSynergyDialog projectId="p" venue={venue} dayType="weekday" scenarioId={null} onOpenChange={() => {}} />
  </QueryClientProvider>);
  expect(screen.getByText(/About 40 shopper visits by the VLM/)).toBeTruthy();   // 24 visitors + 16 affected again
  expect(api.startVlmSynergy).not.toHaveBeenCalled();
});
