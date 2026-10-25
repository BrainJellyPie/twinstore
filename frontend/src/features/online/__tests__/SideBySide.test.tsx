// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { JourneyViewer } from "../JourneyViewer";
import { partingStep } from "../parting";

vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getSession: vi.fn(), getPlayback: vi.fn() }));
const clients: QueryClient[] = [];
beforeEach(() => useLocale.getState().setLocale("en"));
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });

function step(index: number, page: online.PageKind, label: string | null, search = ""): online.SessionStep {
  return { index, url: `/${page}`, page, state: {} as online.BrowserState, options: 3, search_text: search, thought: "",
    choice: label === null ? null : { number: 1, kind: "open_product", label, target: "", ad_id: "" } as online.PageOption,
    seconds: 2, load_seconds: 1, source: "rule", error: "", mark_seed: 0, screen: null, ads: [] };
}

it("finds the first step where two visits differ", () => {
  const shared = [step(0, "home", "Open product: Leash"), step(1, "product", "Add to cart")];
  expect(partingStep(shared, shared)).toBeNull();
  expect(partingStep(shared, [shared[0]!, step(1, "product", "Back")])).toBe(1);
  expect(partingStep([...shared, step(2, "cart", "Checkout")], shared)).toBe(2);
  expect(partingStep([step(0, "home", "Search", "leash")], [step(0, "home", "Search", "lead")])).toBe(0);
});

function view(variant: number, steps: online.SessionStep[], outcome: online.SessionOutcome): online.SessionView {
  return {
    variant, site_id: `s${variant}`, site_name: variant ? "No fee" : "Control",
    shopper: { id: "os0001", device: "desktop", vision: "typical", identity: "Nurse", age_group: "30s", gender: "Female",
      mission: "purchase", goal: "Buy a leash", budget: 0, patience_sec: 300, has_account: false } as online.OnlineShopper,
    session: { shopper_id: "os0001", site_id: `s${variant}`, outcome, order_total: outcome === "purchased" ? 4200 : 0, order: [],
      subtotal: 0, seconds: 30, reached: ["visit"], viewed_products: [], searches: [], exit_page: "cart", exit_thought: "",
      model_requests: 0, fallbacks: 0, survey: null, addon_paid: 0, discount: 0, reminded: false, returned_at: null, steps },
  };
}

it("plays the control and the variant side by side and marks where they part", async () => {
  const shared = [step(0, "home", "Open product: Leash"), step(1, "product", "Add to cart"), step(2, "cart", "Checkout")];
  const views = [view(0, [...shared, step(3, "checkout", "Close the tab")], "left"),
    view(1, [...shared, step(3, "checkout", "Place order"), step(4, "order_complete", null)], "purchased")];
  vi.mocked(online.getSession).mockImplementation(async (_p, _r, variant) => views[variant]!);
  vi.mocked(online.getPlayback).mockResolvedValue([]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  clients.push(client);
  render(
    <QueryClientProvider client={client}>
      <JourneyViewer projectId="p1" runId="r1" variant={1} shopperId="os0001" variants={["Control", "No fee"]}
        currency="USD" compare onVariant={vi.fn()} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("The visits part ways at step 4")).toBeTruthy();
  expect(screen.getByRole("region", { name: "Control" }).textContent).toContain("Left");
  expect(screen.getByRole("region", { name: "No fee" }).textContent).toContain("Ordered · $42.00");
  expect(screen.queryByText("Different from here")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Play from just before" }));
  expect(screen.getAllByText("Step 3 of 4").length + screen.getAllByText("Step 3 of 5").length).toBe(2);
  fireEvent.click(screen.getByRole("button", { name: "Side by side" }));
  expect(screen.queryByText("The visits part ways at step 4")).toBeNull();
});
