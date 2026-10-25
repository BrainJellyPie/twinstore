// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { PageFlow } from "../PageFlow";
import { RunHero } from "../RunHero";
import { ShopperRiver } from "../ShopperRiver";

beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(cleanup);

const summary = (over: Partial<online.VariantSummary>): online.VariantSummary => ({
  site_id: "s1", site_name: "Control", sessions: 3, purchases: 1, conversion: 1 / 3, revenue: 4200, aov: 4200,
  revenue_per_session: 1400, bounce_rate: 0, cart_abandonment: 0, add_to_cart_rate: 0, avg_steps: 0, avg_seconds: 0,
  search_share: 0, zero_result_searches: 0, outcomes: { purchased: 1, left: 1, bounced: 1 }, actions: {}, funnel: [], exits: [],
  segments: [], products: [], searches: [], clicks: [], frictions: [], survey: null, ads: [], recovery: null, ...over,
});

const shopper = (id: string, identity: string) => ({ id, identity, mission: "purchase", goal: "Buy dog food" }) as online.OnlineShopper;

function result(diff: number, low: number, high: number): online.OnlineRunResult {
  return {
    run_id: "r1", name: "Study", policy: "rule", model: "", currency: "USD", notes: [], model_requests: 0, fallbacks: 0, seconds: 1,
    shoppers: [shopper("a", "Teacher"), shopper("b", "Nurse"), shopper("c", "Student")],
    variants: [summary({}), summary({ site_id: "s2", site_name: "Variant", purchases: 2, conversion: 2 / 3 })],
    comparisons: [{ site_id: "s2", site_name: "Variant", ad_lifts: [], segments: [], switches: [], won: 1, lost: 0, changed: 1,
      deltas: [{ metric: "conversion", control: 1 / 3, variant: 2 / 3, diff, ci_low: low, ci_high: high, n: 3 }] }],
    visits: {
      a: [{ outcome: "purchased", order_total: 4200, clicks: 6, rival: null, furthest: "purchase" },
        { outcome: "purchased", order_total: 4200, clicks: 5, rival: null, furthest: "purchase" }],
      b: [{ outcome: "left", order_total: 0, clicks: 3, rival: "purchased", furthest: "add_to_cart" },
        { outcome: "purchased", order_total: 3000, clicks: 7, rival: null, furthest: "purchase" }],
      c: [{ outcome: "bounced", order_total: 0, clicks: 1, rival: null, furthest: "visit" },
        { outcome: "bounced", order_total: 0, clicks: 1, rival: null, furthest: "visit" }],
    },
  };
}

const status = { run_id: "r1", name: "Study", site_ids: ["s1", "s2"], site_names: ["Control", "Variant"], status: "completed",
  phase: "", done: 6, total: 6, error: "", created_at: "", finished_at: "", request: { policy: "rule", shoppers: 3 } } as online.OnlineRunStatus;

function hero(r: online.OnlineRunResult) {
  return render(<RunHero status={status} result={r} wide={false} onWide={vi.fn()} onWatch={vi.fn()} onCompare={null} csvUrl={null}
    onDelete={null} deleting={false} deleteError="" />);
}

it("names a variant that clearly converts better as the winner, and calls a close run too close", () => {
  hero(result(0.33, 0.1, 0.5));
  expect(screen.getByText("Winner: Variant · conversion +33.0 pp")).toBeTruthy();
  expect(screen.getAllByLabelText("Best conversion")).toHaveLength(1);
  cleanup();
  hero(result(0.33, -0.1, 0.5));
  expect(screen.getByText("Too close to call: no clear difference in conversion yet")).toBeTruthy();
  expect(screen.queryByLabelText("Best conversion")).toBeNull();
  cleanup();
  hero(result(-0.33, -0.5, -0.1));
  expect(screen.getByText("Control holds: every variant converts worse")).toBeTruthy();
  expect(screen.getByText("Conversion: 33.3%")).toBeTruthy();  // the final figure is there for screen readers at once
});

it("streams every shopper into each store and opens the visit of a clicked dot", () => {
  const onWatch = vi.fn();
  render(<ShopperRiver result={result(0, 0, 0)} money={(x) => `$${(x / 100).toFixed(2)}`} onWatch={onWatch} />);
  const control = screen.getByRole("group", { name: "Control · Orders: 1 · Visits: 3" });
  const variant = screen.getByRole("group", { name: "Variant · Orders: 2 · Visits: 3" });
  expect(within(control).getAllByRole("button")).toHaveLength(3);
  const nurse = within(variant).getByRole("button", { name: "Nurse: Ordered" });
  fireEvent.pointerEnter(nurse);
  // The same shopper lights up in the other store too, where they left.
  expect(within(control).getByRole("button", { name: "Nurse: Left" }).className).toContain("ring-foreground");
  expect(screen.getByText("Ordered · $30.00")).toBeTruthy();
  fireEvent.click(nurse);
  expect(onWatch).toHaveBeenCalledWith(1, "b");
});

it("draws the page flow with the busiest route and follows a page on hover", () => {
  const flow: online.FlowLink[] = [
    { depth: 0, source: "home", target: "product", outcome: null, sessions: 2 },
    { depth: 0, source: "home", target: null, outcome: "bounced", sessions: 1 },
    { depth: 1, source: "product", target: "order_complete", outcome: null, sessions: 1 },
    { depth: 1, source: "product", target: null, outcome: "left", sessions: 1 },
    { depth: 2, source: "order_complete", target: null, outcome: "purchased", sessions: 1 },
  ];
  const { container } = render(<PageFlow variants={[summary({ flow }), summary({ site_id: "s2", site_name: "Variant", flow: [] })]} />);
  expect(screen.getByRole("img", { name: "Page flow of the visits to Control" })).toBeTruthy();
  const route = screen.getByText("Busiest route:").parentElement!;
  expect(route.textContent).toBe("Busiest route:Home page→Product page→Order confirmed→Ordered");
  // Three page columns, then the ends.
  expect(screen.getByText("Step 3")).toBeTruthy();
  expect(screen.getByText("End")).toBeTruthy();
  expect(container.querySelectorAll("svg[role=img] rect")).toHaveLength(6);
  const panel = screen.getByRole("img").closest("div")!.parentElement!;
  fireEvent.pointerMove(panel, { clientX: 10, clientY: 10 });
  fireEvent.pointerEnter(container.querySelectorAll("svg[role=img] rect")[0]!);
  expect(screen.getByText("Visits: 3 · 100%")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Variant" }));
  expect(screen.getByRole("img", { name: "Page flow of the visits to Variant" })).toBeTruthy();
});
