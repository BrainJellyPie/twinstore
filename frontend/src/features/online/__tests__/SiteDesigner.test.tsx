// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    theme_color: "#2563eb", device: null, grid_columns: 4, products_per_page: 8, hero_banner: true, hero_text: "",
    home_sections: ["categories"], large_text: false, show_ratings: true, show_review_counts: true,
    default_sort: "featured", search: "smart", sponsored_slots: 0, recommendations: "similar", quick_add: false,
    reviews_on_product: true, wishlist: true, urgency: false, social_proof: false, welcome_popup: "none",
    cookie_banner: true, chat_widget: false, shipping_fee: 499, free_shipping_threshold: 3500, coupon_code: "",
    coupon_percent: 0, coupon_public: true, guest_checkout: true, checkout_flow: "multi_step",
    payment_methods: ["card"], one_click_buy: false, service_fee: 0, preselected_addon_percent: 0,
    return_policy: "free_30", trust_badges: true, page_load_ms: 600,
  },
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
