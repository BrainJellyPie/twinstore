// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { RunLauncher } from "../RunLauncher";

vi.mock("@/shared/api/client", () => ({ getModels: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({ ...await original<typeof online>(), getSite: vi.fn(), scanSite: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ Link: () => null }));

const options = {
  page_style: "classic", theme_color: "#2563eb", device: null, grid_columns: 4, products_per_page: 8, hero_banner: true, hero_text: "",
  home_sections: ["categories"], large_text: true, show_ratings: true, show_review_counts: true,
  default_sort: "featured", search: "smart", sponsored_slots: 0, recommendations: "similar", quick_add: true,
  reviews_on_product: true, wishlist: true, urgency: true, social_proof: true, welcome_popup: "none",
  cookie_banner: false, chat_widget: false, shipping_fee: 0, free_shipping_threshold: 0, coupon_code: "",
  coupon_percent: 0, coupon_public: true, guest_checkout: false, checkout_flow: "one_page",
  payment_methods: ["card", "apple_pay", "bnpl"], one_click_buy: false, service_fee: 300, preselected_addon_percent: 0,
  return_policy: "free_30", trust_badges: true, page_load_ms: 200, cart_reminder: true, cart_reminder_percent: 10,
} as online.SiteOptions;
const site = { id: "s1", name: "Shop", currency: "USD", options, products: [], categories: [], ads: [] } as unknown as online.OnlineSite;
const summary = { id: "s1", name: "Shop", currency: "USD", theme_color: "#2563eb", cart_reminder: true } as online.SiteSummary;
const delta = (diff: number, low: number, high: number): online.PairedDelta =>
  ({ metric: "revenue_per_session", control: 500, variant: 500 + diff, diff, ci_low: low, ci_high: high, n: 150 });

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(online.getSite).mockResolvedValue(site);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("screens every applicable change and ticks the clear winners", async () => {
  vi.mocked(online.scanSite).mockImplementation(async (_pid, _id, body) => ({
    shoppers: 150, conversion: 0.3, revenue_per_session: 500, seconds: 3,
    rows: body.candidates.map((c) => ({ id: c.id, won: 4, lost: 1,
      deltas: [c.id === "no_service_fee" ? delta(42, 10, 70) : c.id === "guest_checkout" ? delta(-30, -50, -5) : delta(3, -20, 25)] })),
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><RunLauncher projectId="p1" sites={[summary]} firstSiteId="s1" hasCustomers onStarted={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Scan these changes" }));
  await waitFor(() => expect(screen.getAllByText(/clearly better|clearly worse|unclear/).length).toBeGreaterThan(2));
  const sent = vi.mocked(online.scanSite).mock.calls[0]![2];
  expect(sent.candidates.map((c) => c.id)).toContain("no_service_fee");
  expect(sent.candidates.find((c) => c.id === "no_service_fee")!.options.service_fee).toBe(0);
  // Best first: the clear gain leads the list.
  const boxes = screen.getAllByRole("checkbox").filter((b) => b.closest("fieldset"));
  expect(boxes[0]!.closest("label")!.textContent).toContain("+$0.42 · clearly better");
  fireEvent.click(screen.getByRole("button", { name: "Tick the clear winners" }));
  expect((boxes[0] as HTMLInputElement).checked).toBe(true);
  expect(screen.getAllByRole("checkbox", { checked: true }).filter((b) => b.closest("fieldset"))).toHaveLength(1);
});
