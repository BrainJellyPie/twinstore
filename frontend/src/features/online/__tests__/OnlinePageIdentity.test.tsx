// @vitest-environment jsdom
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { OnlinePage } from "../OnlinePage";

vi.mock("@tanstack/react-router", () => ({ Link: ({ children }: { children: ReactNode }) => <a>{children}</a> }));
vi.mock("@/shared/api/client", async (original) => ({ ...await original<typeof api>(), getProject: vi.fn(), getModels: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(),
  listSites: vi.fn(), listRuns: vi.fn(), listTemplates: vi.fn(), getSite: vi.fn(), getRun: vi.fn(), startRun: vi.fn(),
}));
vi.mock("../BrowserView", () => ({ BrowserView: () => <p>Browser</p> }));
vi.mock("../JourneyViewer", () => ({ JourneyViewer: (props: { runId: string; variant: number; shopperId: string }) =>
  <div role="dialog">{`${props.runId}:${props.variant}:${props.shopperId}`}</div> }));

const sites: online.SiteSummary[] = ["A", "B"].map((name) => ({
  id: `site_${name}`, name: `Shop ${name}`, template_id: "fashion", currency: "USD", categories: 1, products: 1,
  photos: 0, theme_color: "#2563eb", device: null, cart_reminder: false, variant_of: "", note: "", created_at: "", updated_at: "",
}));
const summary: online.VariantSummary = {
  site_id: "site_A", site_name: "Shop A", sessions: 1, purchases: 0, conversion: 0, revenue: 0, aov: 0,
  revenue_per_session: 0, bounce_rate: 0, cart_abandonment: 0, add_to_cart_rate: 0, avg_steps: 0, avg_seconds: 0,
  search_share: 0, zero_result_searches: 0, outcomes: {}, actions: {}, funnel: [], exits: [], segments: [],
  products: [], searches: [], clicks: [], frictions: [], survey: null, ads: [], recovery: null,
};
function run(id: string, variants: number, shoppers: string[]): online.OnlineRunView {
  return {
    status: { run_id: id, name: id, site_ids: sites.slice(0, variants).map((s) => s.id),
      site_names: sites.slice(0, variants).map((s) => s.name), status: "completed", phase: "", done: 1, total: 1,
      error: "", created_at: "", finished_at: "", request: { site_ids: ["site_A"], shoppers: shoppers.length, policy: "rule",
        seed: 1, max_steps: 24, missions: { purchase: 1, browse: 0, compare: 0, deal_hunt: 0, gift: 0, replenish: 0 },
        mobile_share: 0, source: "panel", image_width: 896, shuffle_marks: true, accessibility: "typical", exit_survey: false } },
    result: { run_id: id, name: id, policy: "rule", model: "", currency: "USD", notes: [], model_requests: 0,
      fallbacks: 0, seconds: 0, comparisons: [], variants: sites.slice(0, variants).map((s) => ({ ...summary, site_id: s.id, site_name: s.name })),
      shoppers: shoppers.map((sid) => ({ id: sid, identity: sid, age_group: "20s", gender: "Female", device: "desktop",
        mission: "purchase", goal: "Buy tea", target_category: "tea", target_terms: ["tea"], target_product: "", budget: 100,
        price_sensitivity: 0.5, patience_sec: 300, tech_savvy: 0.5, has_account: false, description: "", persona_id: "",
        vision: "typical", arrival: "direct" })) },
  };
}
const first = run("Old study", 2, ["old_1", "old_2"]);
const second = run("New study", 1, ["new_1"]);
const clients: QueryClient[] = [];
beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getProject).mockResolvedValue({ metadata: { name: "Project", currency: "USD" }, personas: [], setups: [] } as never);
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(online.listSites).mockResolvedValue(sites);
  vi.mocked(online.listRuns).mockResolvedValue([first.status, second.status]);
  vi.mocked(online.listTemplates).mockResolvedValue([]);
  // No suggested edits are needed for a plain one-store run.
  vi.mocked(online.getSite).mockImplementation(() => new Promise(() => {}));
  vi.mocked(online.getRun).mockImplementation(async (_pid, id) => id === first.status.run_id ? first : second);
  vi.mocked(online.startRun).mockRejectedValue(new Error("Offline start probe"));
});
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
  clients.push(client);
  client.setQueryData(online.onlineKeys.run("p1", first.status.run_id), first);
  client.setQueryData(online.onlineKeys.run("p1", second.status.run_id), second);
  render(<QueryClientProvider client={client}><OnlinePage projectId="p1" /></QueryClientProvider>);
  return client;
}

it("starts the newly selected store when switching stores on the simulation tab", async () => {
  mount();
  fireEvent.click(await screen.findByRole("tab", { name: "Simulate" }));
  fireEvent.click(screen.getByRole("button", { name: /Shop B/ }));
  fireEvent.click(screen.getByRole("button", { name: "Start run" }));
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ site_ids: ["site_B"] })));
  await screen.findByText("Offline start probe");
});

it("keeps the active store and form values when a refreshed site list changes order", async () => {
  const client = mount();
  fireEvent.click(await screen.findByRole("tab", { name: "Simulate" }));
  fireEvent.change(screen.getByLabelText("Shoppers"), { target: { value: "77" } });
  await act(async () => { client.setQueryData(online.onlineKeys.sites("p1"), [...sites].reverse()); });
  fireEvent.click(screen.getByRole("button", { name: "Start run" }));
  await waitFor(() => expect(online.startRun).toHaveBeenCalledWith("p1", expect.objectContaining({ site_ids: ["site_A"], shoppers: 77 })));
  await screen.findByText("Offline start probe");
});

it.each([false, true])("resets cached report shopper and variant selection on a new run (open journey: %s)", async (open) => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /Old study/ }));
  fireEvent.change(screen.getByLabelText("Shopper"), { target: { value: "old_2" } });
  fireEvent.change(screen.getByLabelText("Store"), { target: { value: "1" } });
  if (open) {
    fireEvent.click(screen.getByRole("button", { name: "Play the visit" }));
    expect(screen.getByRole("dialog").textContent).toBe("Old study:1:old_2");
  }
  fireEvent.click(screen.getByRole("button", { name: /New study/ }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect((screen.getByLabelText("Shopper") as HTMLSelectElement).value).toBe("new_1");
  fireEvent.click(screen.getByRole("button", { name: "Play the visit" }));
  expect(screen.getByRole("dialog").textContent).toBe("New study:0:new_1");
});
