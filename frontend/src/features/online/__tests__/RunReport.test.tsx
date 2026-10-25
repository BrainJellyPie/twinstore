// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { RunReport } from "../RunReport";

vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getRun: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });

function mount(n: number, diff = 0.04, low: number | null = 0, high: number | null = 0.08) {
  const summary: online.VariantSummary = {
    site_id: "s1", site_name: "Control", sessions: n, purchases: 0, conversion: 0, revenue: 0, aov: 0,
    revenue_per_session: 0, bounce_rate: 0, cart_abandonment: 0, add_to_cart_rate: 0, avg_steps: 0, avg_seconds: 0,
    search_share: 0, zero_result_searches: 0, outcomes: {}, actions: {}, funnel: [], exits: [], segments: [],
    products: [], searches: [], clicks: [], frictions: [], survey: null, ads: [], recovery: null,
  };
  const view: online.OnlineRunView = {
    status: {
      run_id: "r1", name: "Study", site_ids: ["s1", "s2"], site_names: ["Control", "Variant"], status: "completed",
      phase: "", done: 2 * n, total: 2 * n, error: "", created_at: "", finished_at: "",
      request: { site_ids: ["s1", "s2"], shoppers: n, policy: "rule", seed: 1, max_steps: 24,
        missions: { purchase: 1, browse: 0, compare: 0, deal_hunt: 0, gift: 0, replenish: 0 }, mobile_share: 0,
        source: "panel", image_width: 896, shuffle_marks: true, accessibility: "typical", exit_survey: false },
    },
    result: {
      run_id: "r1", name: "Study", policy: "rule", model: "", currency: "USD", notes: [], shoppers: [],
      model_requests: 0, fallbacks: 0, seconds: 0, variants: [summary, { ...summary, site_id: "s2", site_name: "Variant" }],
      comparisons: [{ site_id: "s2", site_name: "Variant", ad_lifts: [], segments: [], switches: [], won: 0, lost: 0,
        changed: 0, deltas: [{ metric: "conversion", control: 0, variant: diff, diff, ci_low: low, ci_high: high, n }] }],
    },
  };
  vi.mocked(online.getRun).mockResolvedValue(view);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(<QueryClientProvider client={client}><RunReport projectId="p1" runId="r1" onDeleted={vi.fn()} /></QueryClientProvider>);
}

it("reports the run limit when the next estimate crosses 500 instead of recommending 501", async () => {
  mount(500);
  await screen.findByText("Study");
  expect(screen.queryByText(/about 501/)).toBeNull();
  expect(screen.getByText(/limit of 500 shoppers per store/)).toBeTruthy();
});

it.each([[499, 500], [100, 101]])("allows a feasible estimate above the current %s shoppers", async (n, expected) => {
  mount(n);
  expect(await screen.findByText(new RegExp(`about ${expected}`))).toBeTruthy();
});

it("does not infer business importance from an estimate above the run limit", async () => {
  mount(100, 0.001, -0.1, 0.1);
  await screen.findByText("Study");
  expect(screen.queryByText(/probably not one that matters/)).toBeNull();
  expect(screen.getByText(/limit of 500 shoppers per store/)).toBeTruthy();
});

it.each([[1, 0.04, null, null], [100, 0, -0.1, 0.1], [100, 0.04, 0.01, 0.09]])(
  "omits unsupported or unnecessary planning estimates", async (n, diff, low, high) => {
    mount(n!, diff!, low, high);
    await screen.findByText("Study");
    expect(screen.queryByText(/about \d+|limit of 500 shoppers per store/)).toBeNull();
  },
);
