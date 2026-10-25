// @vitest-environment jsdom
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { JourneyViewer } from "../JourneyViewer";
import { RunReport } from "../RunReport";

vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getRun: vi.fn(), getSession: vi.fn(), deleteRun: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });

function client() {
  const c = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(c);
  return c;
}

const summary: online.VariantSummary = {
  site_id: "s1", site_name: "Control", sessions: 40, purchases: 10, conversion: 0.25, revenue: 0, aov: 0,
  revenue_per_session: 0, bounce_rate: 0, cart_abandonment: 0, add_to_cart_rate: 0, avg_steps: 0, avg_seconds: 0,
  search_share: 0, zero_result_searches: 0, outcomes: {}, actions: {}, funnel: [], exits: [], segments: [],
  products: [], searches: [], clicks: [], frictions: [], survey: null, ads: [], recovery: null,
  rival: { left: 30, went: 12, bought: 6, revenue: 24000 },
};

function mountReport(rivalName: string) {
  const view: online.OnlineRunView = {
    status: {
      run_id: "r1", name: "Study", site_ids: ["s1", "s2"], site_names: ["Control", "Variant"], status: "completed",
      phase: "", done: 120, total: 120, error: "", created_at: "", finished_at: "",
      request: { site_ids: ["s1", "s2"], rival_site_id: "s9", shoppers: 40, policy: "rule", seed: 1, max_steps: 24,
        missions: { purchase: 1, browse: 0, compare: 0, deal_hunt: 0, gift: 0, replenish: 0 }, mobile_share: 0,
        source: "panel", image_width: 896, shuffle_marks: true, accessibility: "typical", exit_survey: false },
    },
    result: {
      run_id: "r1", name: "Study", policy: "rule", model: "", currency: "USD", notes: [], shoppers: [],
      model_requests: 0, fallbacks: 0, seconds: 0, rival_name: rivalName,
      variants: [summary, { ...summary, site_id: "s2", site_name: "Variant", rival: { left: 20, went: 8, bought: 2, revenue: 8000 } }],
      comparisons: [{ site_id: "s2", site_name: "Variant", ad_lifts: [], segments: [], switches: [], won: 0, lost: 0, changed: 0,
        deltas: [{ metric: "rival_revenue_per_session", control: 600, variant: 200, diff: -400, ci_low: -700, ci_high: -100, n: 40 }] }],
    },
  };
  vi.mocked(online.getRun).mockResolvedValue(view);
  render(<QueryClientProvider client={client()}><RunReport projectId="p1" runId="r1" onDeleted={vi.fn()} /></QueryClientProvider>);
}

it("shows what the rival took from each store, and less taken as good", async () => {
  mountReport("Rival Pets");
  const section = (await screen.findByText("Where lost shoppers went: Rival Pets")).closest("section")!;
  const rows = within(section).getAllByRole("row");
  expect(rows[1]!.textContent).toContain("Control");
  expect(rows[1]!.textContent).toContain("30 · 75.0%");
  expect(rows[1]!.textContent).toContain("12 · 40.0%");
  expect(rows[1]!.textContent).toContain("$240.00");
  expect(rows[2]!.textContent).toContain("$80.00");
  const row = screen.getByText("Rival’s revenue per visit").parentElement!;
  expect(row.textContent).toContain("−$4.00");
  expect(within(row).getByText("Clearly better").className).toContain("text-positive");
});

it("has no rival section without a rival shop", async () => {
  mountReport("");
  await screen.findByText("Study");
  expect(screen.queryByText(/Where lost shoppers went/)).toBeNull();
});

function sessionView(variant: number, siteName: string, rival: online.RivalVisit | null): online.SessionView {
  return {
    variant, site_id: `s${variant}`, site_name: siteName,
    shopper: {
      id: "os0001", identity: "Student", age_group: "20s", gender: "Female", device: "desktop", mission: "purchase",
      goal: "Buy dog food", target_category: "", target_terms: [], target_product: "", budget: 5000, price_sensitivity: 0.5,
      patience_sec: 300, tech_savvy: 0.5, has_account: false, description: "", persona_id: "", vision: "typical",
      arrival: variant === 2 ? "search_engine" : "direct",
    } as online.OnlineShopper,
    session: {
      shopper_id: "os0001", site_id: `s${variant}`, outcome: rival ? "left" : "purchased", order: [], subtotal: 0,
      order_total: rival ? 0 : 4200, seconds: 30, reached: ["visit"], viewed_products: [], searches: [], exit_page: "home",
      exit_thought: "", model_requests: 0, fallbacks: 0, survey: null, addon_paid: 0, discount: 0, reminded: false,
      returned_at: null, rival,
      steps: [{ index: 0, url: "/", page: "home", state: {} as online.BrowserState, options: 3, choice: null, search_text: "",
        thought: "", seconds: 1, load_seconds: 1, source: "rule", error: "", mark_seed: 0, screen: null, ads: [] }],
    },
  };
}

it("tells where a lost shopper went and opens that visit on the rival tab", async () => {
  const views = [sessionView(0, "Control", { outcome: "purchased", order_total: 4200, steps: 5, exit_thought: "" }),
    sessionView(1, "Variant", null), sessionView(2, "Rival Pets", null)];
  vi.mocked(online.getSession).mockImplementation(async (_p, _r, variant) => views[variant]!);
  const onVariant = vi.fn();
  const view = (variant: number) => (
    <QueryClientProvider client={client()}>
      <JourneyViewer projectId="p1" runId="r1" variant={variant} shopperId="os0001" variants={["Control", "Variant"]}
        rival="Rival Pets" currency="USD" onVariant={onVariant} onClose={vi.fn()} />
    </QueryClientProvider>
  );
  const { rerender } = render(view(0));
  expect(await screen.findByText(/Then tried Rival Pets: Ordered/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Rival Pets (rival)" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Replay that visit" }));
  expect(onVariant).toHaveBeenCalledWith(2);
  rerender(view(2));
  expect((await screen.findByRole("button", { name: "Rival Pets (rival)" })).getAttribute("aria-pressed")).toBe("true");
  expect(screen.queryByText(/Then tried/)).toBeNull();
});

it("offers the visit as a GIF download", async () => {
  vi.mocked(online.getSession).mockResolvedValue(sessionView(1, "Variant", null));
  render(
    <QueryClientProvider client={client()}>
      <JourneyViewer projectId="p1" runId="r1" variant={1} shopperId="os0001" variants={["Control", "Variant"]}
        currency="USD" onVariant={vi.fn()} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
  const link = await screen.findByRole("link", { name: "Download GIF" });
  expect(link.getAttribute("href")).toMatch(/\/api\/projects\/p1\/online\/runs\/r1\/sessions\/1\/os0001\/replay\.gif$/);
  expect(link.hasAttribute("download")).toBe(true);
});

it("does not fetch a run again after deleting it", async () => {
  mountReport("");
  await screen.findByText("Study");
  cleanup();
  // Like the online page: a deleted run's report goes away.
  function Page() {
    const [open, setOpen] = useState(true);
    return open ? <RunReport projectId="p1" runId="r1" onDeleted={() => setOpen(false)} /> : <p>No run</p>;
  }
  vi.mocked(online.getRun).mockClear();
  vi.mocked(online.deleteRun).mockResolvedValue(undefined as never);
  render(<QueryClientProvider client={client()}><Page /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  await screen.findByText("No run");
  await new Promise((r) => setTimeout(r, 50));
  expect(online.getRun).toHaveBeenCalledTimes(1);
});
