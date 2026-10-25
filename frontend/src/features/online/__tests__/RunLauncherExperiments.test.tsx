// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { RunLauncher } from "../RunLauncher";

vi.mock("@/shared/api/client", () => ({ getModels: vi.fn() }));
vi.mock("@/shared/api/online", async (original) => ({
  ...await original<typeof online>(), getSite: vi.fn(), copySite: vi.fn(), startRun: vi.fn(),
}));
vi.mock("@tanstack/react-router", () => ({ Link: () => null }));
const source: online.OnlineSite = {
  id: "s1", name: "Shop", template_id: "fashion", currency: "USD", tagline: "", variant_of: "", note: "",
  created_at: "before", updated_at: "before", categories: [{ id: "c", name: "Clothing", glyph: "shirt" }],
  products: [{ id: "p1", name: "Shirt", category_id: "c", price: 1299, list_price: 1599, rating: 4.2, reviews: 5,
    badges: [], stock: 8, description: "", tags: [], image_url: "", weekly_sales: 4, sku: "shirt" }],
  options: {
    page_style: "classic", theme_color: "#2563eb", device: null, grid_columns: 4, products_per_page: 8, hero_banner: true, hero_text: "",
    home_sections: ["categories"], large_text: false, show_ratings: true, show_review_counts: true,
    default_sort: "featured", search: "smart", sponsored_slots: 0, recommendations: "similar", quick_add: false,
    reviews_on_product: true, wishlist: true, urgency: false, social_proof: false, welcome_popup: "none",
    cookie_banner: true, chat_widget: false, shipping_fee: 499, free_shipping_threshold: 3500, coupon_code: "",
    coupon_percent: 0, coupon_public: true, guest_checkout: false, checkout_flow: "multi_step",
    payment_methods: ["card"], one_click_buy: false, service_fee: 300, preselected_addon_percent: 0,
    return_policy: "free_30", trust_badges: true, page_load_ms: 600, cart_reminder: false, cart_reminder_percent: 0,
  },
  ads: [],
};

const summary: online.SiteSummary = {
  ...source, categories: 1, products: 1, photos: 0, theme_color: source.options.theme_color, device: null,
};
const clients: QueryClient[] = [];
beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(api.getModels).mockResolvedValue([]);
  vi.mocked(online.getSite).mockResolvedValue(source);
  vi.mocked(online.copySite).mockImplementation(async (_pid, _id, body) => ({
    ...source, name: body.name ?? source.name, options: body.options ?? source.options,
    id: body.options?.service_fee === 0 ? "copy_fee" : "copy_guest", variant_of: source.id,
  }));
  vi.mocked(online.startRun).mockRejectedValue(new Error("Local model is unavailable"));
});
afterEach(() => { cleanup(); clients.splice(0).forEach((c) => c.clear()); vi.resetAllMocks(); });
function mount(initialSites: online.SiteSummary[] = [summary]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  clients.push(client);
  const view = (sites: online.SiteSummary[]) => <QueryClientProvider client={client}>
    <RunLauncher projectId="p1" sites={sites} firstSiteId="s1" hasCustomers onStarted={vi.fn()} />
  </QueryClientProvider>;
  const rendered = render(view(initialSites));
  return (sites: online.SiteSummary[]) => rendered.rerender(view(sites));
}
function start() {
  return screen.getByRole("button", { name: /^(Start run|Create the variants and compare|Compare)/ }) as HTMLButtonElement;
}
async function pick() {
  fireEvent.click(await screen.findByRole("checkbox", { name: "Drop the last-step service fee" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Allow guest checkout" }));
}

it.each(["first_copy", "copy", "start"])("reuses confirmed variants when %s fails and the run is retried", async (failure) => {
  if (failure === "first_copy") vi.mocked(online.copySite).mockRejectedValueOnce(new Error("Copy failed"));
  if (failure === "copy") vi.mocked(online.copySite)
    .mockResolvedValueOnce({ ...source, id: "copy_fee", name: "Fee variant" })
    .mockRejectedValueOnce(new Error("Copy failed"));
  mount();
  await pick();
  fireEvent.click(start());
  await screen.findByRole("alert");
  await waitFor(() => expect(start().disabled).toBe(false));
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledTimes(failure === "start" ? 2 : 1));
  expect(online.copySite).toHaveBeenCalledTimes(failure === "start" ? 2 : 3);
  expect(online.startRun).toHaveBeenLastCalledWith("p1", expect.objectContaining({
    site_ids: ["s1", "copy_fee", "copy_guest"],
  }));
});

it("shows a created variant immediately after a failure and deduplicates a later store refresh", async () => {
  vi.mocked(online.copySite).mockResolvedValue({ ...source, id: "copy_fee", name: "Fee variant" });
  const refresh = mount();
  fireEvent.click(await screen.findByRole("checkbox", { name: "Drop the last-step service fee" }));
  fireEvent.click(start());
  await screen.findByRole("alert");
  const created = screen.getByRole("checkbox", { name: /^Fee variant/ }) as HTMLInputElement;
  expect(created.checked).toBe(true);
  refresh([summary, { ...summary, id: "copy_fee", name: "Fee variant" }]);
  expect(screen.getAllByRole("checkbox", { name: /^Fee variant/ })).toHaveLength(1);
  fireEvent.click(created);
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledTimes(2));
  expect(online.startRun).toHaveBeenLastCalledWith("p1", expect.objectContaining({ site_ids: ["s1"] }));
  expect(online.copySite).toHaveBeenCalledTimes(1);
});

it("locks the compared stores and experiments while a variant is being created", async () => {
  let resolve: (value: online.OnlineSite) => void = () => {};
  vi.mocked(online.copySite).mockReturnValue(new Promise((done) => { resolve = done; }));
  mount();
  fireEvent.click(await screen.findByRole("checkbox", { name: "Drop the last-step service fee" }));
  fireEvent.click(start());
  await waitFor(() => expect(online.copySite).toHaveBeenCalledOnce());
  expect((screen.getByRole("checkbox", { name: /^Shop/ }) as HTMLInputElement).disabled).toBe(true);
  expect(screen.getByRole("checkbox", { name: "Allow guest checkout" }).matches(":disabled")).toBe(true);
  await act(async () => resolve({ ...source, id: "copy_fee", name: "Fee variant" }));
  await screen.findByRole("alert");
  await waitFor(() => expect(start().disabled).toBe(false));
  expect((screen.getByRole("checkbox", { name: /^Shop/ }) as HTMLInputElement).disabled).toBe(false);
});

it.each([
  [false, 3, false], [false, 3, true], [true, 3, false], [true, 3, true],
  [false, 24, false], [false, 24, true], [true, 24, false], [true, 24, true],
] as const)("bounds model work for reminder=%s, steps=%s, survey=%s", async (reminder, steps, survey) => {
  vi.mocked(online.getSite).mockResolvedValue({ ...source, options: { ...source.options, cart_reminder: reminder } });
  mount([{ ...summary, cart_reminder: reminder }]);
  await screen.findByRole("checkbox", { name: "Drop the last-step service fee" });
  fireEvent.click(screen.getByRole("radio", { name: /^Text model/ }));
  fireEvent.change(screen.getByLabelText(/^Max clicks/), { target: { value: String(steps) } });
  if (!survey) fireEvent.click(screen.getByRole("checkbox", { name: "Exit survey" }));
  const estimate = screen.getByText(/^Model (calls|decisions)/).textContent;
  const responses = survey ? 1 : 0;
  expect(estimate).toContain(`about ${(30 * (Math.min(4, steps) + responses)).toLocaleString("en")},`);
  expect(estimate).toContain(`at most ${(30 * (steps * (reminder ? 2 : 1) + responses)).toLocaleString("en")}.`);
});

it("includes reminder experiments and an unknown selected store in the upper estimate", async () => {
  mount([{ ...summary, cart_reminder: false }, { ...summary, id: "s2", name: "Other store" }]);
  fireEvent.click(await screen.findByRole("checkbox", { name: "Send a cart reminder email" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Other store" }));
  fireEvent.click(screen.getByRole("radio", { name: /^Text model/ }));
  expect(screen.getByText(/^Model (calls|decisions)/).textContent).toContain("at most 3,690.");
});

it("creates a price experiment with the repriced catalog in the same copy request", async () => {
  mount();
  fireEvent.click(await screen.findByRole("checkbox", { name: "All prices 10% lower" }));
  fireEvent.click(start());
  await screen.findByRole("alert");
  expect(online.copySite).toHaveBeenCalledExactlyOnceWith("p1", "s1", expect.objectContaining({
    options: source.options, products: [{ ...source.products[0], price: 1169 }],
  }));
  expect(source.products[0]?.price).toBe(1299);
  fireEvent.click(start());
  await waitFor(() => expect(online.startRun).toHaveBeenCalledTimes(2));
  expect(online.copySite).toHaveBeenCalledTimes(1);
});
