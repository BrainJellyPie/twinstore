// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as online from "@/shared/api/online";
import { useLocale } from "@/shared/i18n/i18n";
import { SiteDesigner } from "../SiteDesigner";

vi.mock("@/shared/api/online", async (original) => ({
  ...await original<typeof online>(), getSite: vi.fn(), copySite: vi.fn(), saveSite: vi.fn(), deleteSite: vi.fn(),
}));

const source: online.OnlineSite = {
  id: "s1", name: "Control", template_id: "fashion", currency: "USD", tagline: "", variant_of: "", note: "",
  created_at: "before", updated_at: "before", categories: [{ id: "c", name: "Clothing", glyph: "shirt" }],
  products: [{ id: "p1", name: "Shirt", category_id: "c", price: 1299, list_price: 1599, rating: 4.2, reviews: 5,
    badges: [], stock: 8, description: "", tags: [], image_url: "", weekly_sales: 4, sku: "shirt" }],
  options: {
    page_style: "classic", theme_color: "#2563eb", device: null, grid_columns: 4, products_per_page: 8, hero_banner: true, hero_text: "",
    home_sections: ["categories"], large_text: false, show_ratings: true, show_review_counts: true,
    default_sort: "featured", search: "smart", sponsored_slots: 0, recommendations: "similar", quick_add: false,
    reviews_on_product: true, wishlist: true, urgency: false, social_proof: false, welcome_popup: "none",
    cookie_banner: true, chat_widget: false, shipping_fee: 499, free_shipping_threshold: 3500, coupon_code: "",
    coupon_percent: 0, coupon_public: true, guest_checkout: true, checkout_flow: "multi_step",
    payment_methods: ["card"], one_click_buy: false, service_fee: 0, preselected_addon_percent: 0,
    return_policy: "free_30", trust_badges: true, page_load_ms: 600, cart_reminder: false, cart_reminder_percent: 0,
  },
  ads: [],
};

beforeEach(() => {
  useLocale.getState().setLocale("en");
  vi.mocked(online.getSite).mockResolvedValue(source);
  vi.mocked(online.copySite).mockImplementation(async () => ({ ...source, id: "variant", variant_of: source.id }));
  vi.mocked(online.saveSite).mockRejectedValue(new Error("The second write failed"));
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function mount() {
  const copied = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <SiteDesigner projectId="p1" siteId="s1" onCopied={copied} onDeleted={vi.fn()} />
  </QueryClientProvider>);
  return copied;
}

it.each(["USD", "KRW", "JPY"])("saves edited %s products and options in one variant request", async (currency) => {
  vi.mocked(online.getSite).mockResolvedValue({ ...source, currency });
  const copied = mount();
  fireEvent.change(await screen.findByRole("textbox", { name: "Shirt: Price" }), { target: { value: "7" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Stock" }), { target: { value: "2" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Product" }), { target: { value: "Edited shirt" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Store name" }), { target: { value: "Draft variant" } });
  fireEvent.click(screen.getByRole("button", { name: "Save as a variant" }));
  await waitFor(() => expect(copied).toHaveBeenCalledWith("variant"));
  expect(online.copySite).toHaveBeenCalledExactlyOnceWith("p1", "s1", expect.objectContaining({
    name: "Draft variant", options: source.options,
    products: [{ ...source.products[0], name: "Edited shirt", price: currency === "USD" ? 700 : 7, stock: 2 }],
  }));
  expect(online.saveSite).not.toHaveBeenCalled();
  expect(source.products[0]?.price).toBe(1299);
});

it("keeps the draft visible when creating the variant fails", async () => {
  vi.mocked(online.copySite).mockRejectedValue(new Error("The worker is busy"));
  const copied = mount();
  const name = await screen.findByRole("textbox", { name: "Product" });
  fireEvent.change(name, { target: { value: "Edited shirt" } });
  fireEvent.click(screen.getByRole("button", { name: "Save as a variant" }));
  expect((await screen.findByRole("alert")).textContent).toContain("The worker is busy");
  expect((name as HTMLInputElement).value).toBe("Edited shirt");
  expect(name.matches(":disabled")).toBe(false);
  expect(copied).not.toHaveBeenCalled();
  expect(online.saveSite).not.toHaveBeenCalled();
});

it.each(["", "wrong", "-1", "9,99", "1e2", "9007199254740992"])("blocks both saves for invalid price %j until corrected", async (text) => {
  mount();
  const price = await screen.findByRole("textbox", { name: "Shirt: Price" });
  fireEvent.change(price, { target: { value: text } });
  expect(price.getAttribute("aria-invalid")).toBe("true");
  const save = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
  const variant = screen.getByRole("button", { name: "Save as a variant" }) as HTMLButtonElement;
  expect(save.disabled).toBe(true);
  expect(variant.disabled).toBe(true);
  fireEvent.click(save);
  fireEvent.click(variant);
  expect(online.saveSite).not.toHaveBeenCalled();
  expect(online.copySite).not.toHaveBeenCalled();
  fireEvent.change(price, { target: { value: "0" } });
  expect(price.getAttribute("aria-invalid")).toBeNull();
  expect(save.disabled).toBe(false);
  expect(variant.disabled).toBe(false);
});

it.each(["Delivery fee", "Free delivery from", "Service fee at the last step", "Shirt: Was (struck through)"])("blocks invalid %s amounts too", async (label) => {
  mount();
  fireEvent.change(await screen.findByRole("textbox", { name: label }), { target: { value: "invalid" } });
  expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Save as a variant" }) as HTMLButtonElement).disabled).toBe(true);
});

it("retains an invalid price when a filter temporarily hides the product", async () => {
  mount();
  fireEvent.change(await screen.findByRole("textbox", { name: "Shirt: Price" }), { target: { value: "invalid" } });
  const filter = screen.getByRole("textbox", { name: "Find a product" });
  fireEvent.change(filter, { target: { value: "nothing matches" } });
  expect(screen.queryByRole("textbox", { name: "Shirt: Price" })).toBeNull();
  expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(filter, { target: { value: "" } });
  const price = screen.getByRole("textbox", { name: "Shirt: Price" }) as HTMLInputElement;
  expect(price.value).toBe("invalid");
  fireEvent.change(price, { target: { value: "7.25" } });
  expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(false);
});

it("keeps saving blocked until every invalid amount has been corrected", async () => {
  mount();
  const price = await screen.findByRole("textbox", { name: "Shirt: Price" });
  const delivery = screen.getByRole("textbox", { name: "Delivery fee" });
  fireEvent.change(price, { target: { value: "wrong" } });
  fireEvent.change(delivery, { target: { value: "wrong" } });
  fireEvent.change(price, { target: { value: "7" } });
  expect((screen.getByRole("button", { name: "Save as a variant" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(delivery, { target: { value: "0" } });
  expect((screen.getByRole("button", { name: "Save as a variant" }) as HTMLButtonElement).disabled).toBe(false);
});

const ad: online.AdCampaign = {
  id: "ad1", name: "Shirt banner", product_id: "p1", placement: "hero_banner", headline: "", pricing: "cpc", cost: 50, active: true,
};

it("sends a variant's ads with the copy, and a version without ads pauses every ad", async () => {
  vi.mocked(online.getSite).mockResolvedValue({ ...source, ads: [ad] });
  vi.mocked(online.saveSite).mockImplementation(async (_pid, site) => site);
  const copied = mount();
  fireEvent.change(await screen.findByRole("textbox", { name: "Ad name" }), { target: { value: "Renamed banner" } });
  fireEvent.click(screen.getByRole("button", { name: "Save as a variant" }));
  await waitFor(() => expect(copied).toHaveBeenCalledWith("variant"));
  const renamed = { ...ad, name: "Renamed banner" };
  expect(online.copySite).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ ads: [renamed] }));
  expect(online.saveSite).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Make a version without ads" }));
  await waitFor(() => expect(online.copySite).toHaveBeenCalledTimes(2));
  // The store is saved first, so the copy differs from it only in its ads.
  expect(online.saveSite).toHaveBeenCalledExactlyOnceWith("p1", expect.objectContaining({ id: "s1", ads: [renamed] }));
  expect(online.copySite).toHaveBeenLastCalledWith("p1", "s1", expect.objectContaining({ ads: [{ ...renamed, active: false }] }));
});

it("blocks saving while an ad cost is invalid, until the ad is fixed or removed", async () => {
  vi.mocked(online.getSite).mockResolvedValue({ ...source, ads: [ad] });
  mount();
  const cost = await screen.findByRole("textbox", { name: "Cost per click" });
  fireEvent.change(cost, { target: { value: "lots" } });
  expect(cost.getAttribute("aria-invalid")).toBe("true");
  expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole("button", { name: "Make a version without ads" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Remove ad" }));
  expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(false);
});

it("does not fetch a store again after deleting it", async () => {
  vi.mocked(online.deleteSite).mockResolvedValue(undefined as never);
  const deleted = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <SiteDesigner projectId="p1" siteId="s1" onCopied={vi.fn()} onDeleted={deleted} />
  </QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete this store" }));
  await waitFor(() => expect(deleted).toHaveBeenCalledTimes(1));
  await new Promise((r) => setTimeout(r, 50));
  expect(online.getSite).toHaveBeenCalledTimes(1);
  expect(client.getQueryCache().find({ queryKey: online.onlineKeys.site("p1", "s1") })).toBeUndefined();
});

it.each(["Save", "Save as a variant", "Make a version without ads"])(
  "prevents editing or deleting a draft while %s is pending", async (action) => {
    vi.mocked(online.getSite).mockResolvedValue({ ...source, ads: [ad] });
    vi.mocked(online.saveSite).mockImplementation(() => new Promise(() => {}));
    vi.mocked(online.copySite).mockImplementation(() => new Promise(() => {}));
    mount();
    const name = await screen.findByRole("textbox", { name: "Store name" });
    fireEvent.change(name, { target: { value: "Reviewed draft" } });
    fireEvent.click(screen.getByRole("button", { name: action }));
    await waitFor(() => expect(action === "Save as a variant" ? online.copySite : online.saveSite).toHaveBeenCalledTimes(1));
    // Native clicks respect a disabled fieldset, including the secondary actions.
    await act(async () => screen.getByRole("button", { name: "Delete" }).click());
    const confirm = screen.queryByRole("button", { name: "Delete this store" });
    if (confirm) await act(async () => confirm.click());
    expect(online.deleteSite).not.toHaveBeenCalled();
    expect(name.matches(":disabled")).toBe(true);
    expect(screen.getByRole("textbox", { name: "Shirt: Price" }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Save" }).matches(":disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Save as a variant" }).matches(":disabled")).toBe(true);
  },
);

it("keeps the draft locked until the saved snapshot has refreshed", async () => {
  const saved = { ...source, name: "Reviewed draft", updated_at: "after" };
  let finishRefresh!: (site: online.OnlineSite) => void;
  vi.mocked(online.getSite).mockResolvedValueOnce(source).mockImplementation(
    () => new Promise((resolve) => { finishRefresh = resolve; }),
  );
  vi.mocked(online.saveSite).mockResolvedValue(saved);
  mount();
  fireEvent.change(await screen.findByRole("textbox", { name: "Store name" }), { target: { value: saved.name } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(vi.mocked(online.getSite).mock.calls.length).toBeGreaterThanOrEqual(2));
  expect(screen.getByRole("textbox", { name: "Store name" }).matches(":disabled")).toBe(true);
  await act(async () => finishRefresh(saved));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Store name" }).matches(":disabled")).toBe(false));
  const name = screen.getByRole("textbox", { name: "Store name" }) as HTMLInputElement;
  expect(name.value).toBe(saved.name);
  fireEvent.change(name, { target: { value: "Next edit" } });
  fireEvent.click(screen.getByRole("button", { name: "Save as a variant" }));
  await waitFor(() => expect(online.copySite).toHaveBeenCalledWith("p1", "s1", expect.objectContaining({ name: "Next edit" })));
});

it.each(["Save", "Make a version without ads"])("unlocks the unchanged draft after %s fails", async (action) => {
  vi.mocked(online.getSite).mockResolvedValue({ ...source, ads: [ad] });
  mount();
  const price = await screen.findByRole("textbox", { name: "Shirt: Price" }) as HTMLInputElement;
  fireEvent.change(price, { target: { value: "7.25" } });
  fireEvent.click(screen.getByRole("button", { name: action }));
  expect((await screen.findByRole("alert")).textContent).toContain("The second write failed");
  expect(price.value).toBe("7.25");
  expect(price.matches(":disabled")).toBe(false);
  vi.mocked(online.saveSite).mockImplementation(async (_pid, site) => site);
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(online.saveSite).toHaveBeenCalledTimes(2));
  expect(online.saveSite).toHaveBeenLastCalledWith("p1", expect.objectContaining({
    products: [expect.objectContaining({ price: 725 })],
  }));
});

it("does not save or copy a store while its deletion is pending", async () => {
  vi.mocked(online.deleteSite).mockImplementation(() => new Promise(() => {}));
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
  fireEvent.click(screen.getByRole("button", { name: "Delete this store" }));
  await waitFor(() => expect(online.deleteSite).toHaveBeenCalledTimes(1));
  await act(async () => {
    screen.getByRole("button", { name: "Save" }).click();
    screen.getByRole("button", { name: "Save as a variant" }).click();
  });
  expect(online.saveSite).not.toHaveBeenCalled();
  expect(online.copySite).not.toHaveBeenCalled();
  expect(screen.getByRole("textbox", { name: "Store name" }).matches(":disabled")).toBe(true);
});

it("shows the store in every page style and saves a picked style as a variant", async () => {
  const copied = mount();
  const styles = await screen.findByRole("radiogroup", { name: "Page style" });
  const neon = screen.getByRole("radio", { name: /Neon/ });
  expect(screen.getAllByRole("radio")).toHaveLength(online.PAGE_STYLES.length);
  expect(screen.getByRole("radio", { name: /Classic/ }).getAttribute("aria-checked")).toBe("true");
  expect(neon.querySelector("img")!.getAttribute("src")).toMatch(/\/sites\/s1\/preview\.png\?device=desktop&v=before&style=neon$/);
  expect(styles.textContent).toContain("In use");
  fireEvent.click(neon);
  expect(neon.getAttribute("aria-checked")).toBe("true");
  expect(neon.textContent).toContain("Selected, not saved yet");
  fireEvent.click(screen.getByRole("button", { name: "Save as a variant" }));
  await waitFor(() => expect(copied).toHaveBeenCalledWith("variant"));
  expect(online.copySite).toHaveBeenCalledWith("p1", "s1", expect.objectContaining({ options: { ...source.options, page_style: "neon" } }));
});
