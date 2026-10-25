import { describe, expect, it } from "vitest";

import type { OnlineProduct, OnlineSite, SiteOptions } from "@/shared/api/online";
import { messages } from "@/shared/i18n/messages";

import { experimentsFor, QUICK_EXPERIMENTS } from "../experiments";

const OPTIONS: SiteOptions = {
  theme_color: "#2563eb", device: null, grid_columns: 4, products_per_page: 8, hero_banner: true, hero_text: "",
  home_sections: ["categories", "bestsellers"], large_text: false, show_ratings: true, show_review_counts: true,
  default_sort: "featured", search: "exact", sponsored_slots: 2, recommendations: "similar", quick_add: false,
  reviews_on_product: true, wishlist: true, urgency: true, social_proof: false, welcome_popup: "newsletter",
  cookie_banner: true, chat_widget: false, shipping_fee: 499, free_shipping_threshold: 3500, coupon_code: "",
  coupon_percent: 0, coupon_public: true, guest_checkout: false, checkout_flow: "multi_step", payment_methods: ["card"],
  one_click_buy: false, service_fee: 300, preselected_addon_percent: 10, return_policy: "paid", trust_badges: true,
  page_load_ms: 800, cart_reminder: false, cart_reminder_percent: 0,
};

const product = (id: string, price: number, weekly_sales: number, list_price = 0): OnlineProduct => ({
  id, name: id, category_id: "c", price, list_price, rating: 4, reviews: 3, badges: [], stock: null, description: "",
  tags: [], image_url: "", weekly_sales, sku: id,
});
const PRODUCTS = [product("a", 1299, 50, 1599), product("b", 999, 40), product("c", 450, 30), product("d", 2500, 20),
  product("e", 120, 10), product("f", 3000, 1)];

function site(options: SiteOptions = OPTIONS, currency = "USD", products = PRODUCTS): OnlineSite {
  return { id: "s", name: "Shop", template_id: "fashion", currency, tagline: "", categories: [], products, options, ads: [],
    variant_of: "", note: "", created_at: "", updated_at: "" };
}

describe("quick experiments", () => {
  it.each([
    ["USD", [0, 1, 17, 100], [0, 1, 15, 90], [0, 1, 19, 110], [0, 1, 14, 80]],
    ["KRW", [0, 50, 170, 1000], [0, 45, 153, 900], [0, 55, 187, 1100], [0, 40, 136, 800]],
    ["JPY", [0, 3, 17, 100], [0, 3, 15, 90], [0, 3, 19, 110], [0, 2, 14, 80]],
  ] as const)("preserves free products and existing fine %s prices", (currency, prices, down, up, deals) => {
    const products = prices.map((price, i) => product(`p${i}`, price, 10 - i));
    const before = structuredClone(products);
    const found = Object.fromEntries(experimentsFor(site(OPTIONS, currency, products)).map((x) => [x.id, x.products]));
    expect(found.prices_down?.map((p) => p.price)).toEqual(down);
    expect(found.prices_up?.map((p) => p.price)).toEqual(up);
    expect(found.best_seller_deals?.map((p) => p.price)).toEqual(deals);
    expect(products).toEqual(before);
  });

  it.each(["USD", "KRW", "JPY"])("omits %s price experiments that would change no price", (currency) => {
    for (const price of [0, 1]) {
      const products = [product("p", price, 10)];
      const found = experimentsFor(site(OPTIONS, currency, products));
      expect(found.map((x) => x.id)).not.toContain("prices_down");
      expect(found.map((x) => x.id)).not.toContain("prices_up");
      expect(found.map((x) => x.id)).not.toContain("best_seller_deals");
      expect(products[0]?.list_price).toBe(0);
    }
  });

  it.each(["USD", "KRW", "JPY"])("keeps %s price changes in the requested direction across rounding boundaries", (currency) => {
    for (const price of [0, 1, 3, 9, 10, 17, 50, 99, 100, 149, 170, 500, 999, 1000]) {
      const products = [product("p", price, 10)];
      for (const x of experimentsFor(site(OPTIONS, currency, products)).filter((x) => x.products)) {
        const after = x.products![0]!.price;
        expect(Number.isInteger(after)).toBe(true);
        expect(after).toBeGreaterThanOrEqual(0);
        if (x.id === "prices_up") expect(after).toBeGreaterThan(price);
        else expect(after).toBeLessThan(price);
      }
    }
  });

  it("each changes the store it applies to, and has a label", () => {
    const found = experimentsFor(site());
    expect(found.map((x) => x.id)).not.toContain("pressure"); // urgency is already on
    expect(found.map((x) => x.id)).not.toContain("coupon_popup"); // a welcome popup is already on
    for (const x of found) {
      if (x.products) expect(x.products).not.toEqual(PRODUCTS);
      else expect(x.options).not.toEqual(OPTIONS);
      expect(messages[x.label]).toBeDefined();
    }
    const by = Object.fromEntries(found.map((x) => [x.id, x.options]));
    expect(by.no_service_fee?.service_fee).toBe(0);
    expect(by.lower_threshold?.free_shipping_threshold).toBe(2333);
    expect(by.faster?.page_load_ms).toBe(400);
    expect(by.wallets?.payment_methods).toEqual(["card", "apple_pay", "bnpl"]);
    expect(by.no_pressure).toMatchObject({ urgency: false, social_proof: false });
  });

  it("offers no change a store already has", () => {
    const steps = new Set(["faster", "slower", "lower_threshold"]); // these can be applied again
    for (const x of QUICK_EXPERIMENTS) {
      const once = x.change?.(OPTIONS);
      if (once && !steps.has(x.id)) expect(x.change?.({ ...OPTIONS, ...once })).toBeNull();
    }
    const tidy = { ...OPTIONS, service_fee: 0, guest_checkout: true, shipping_fee: 0, page_load_ms: 200 };
    const ids = experimentsFor(site(tidy)).map((x) => x.id);
    for (const id of ["no_service_fee", "guest_checkout", "free_delivery", "lower_threshold", "faster"]) expect(ids).not.toContain(id);
  });

  it("gives a welcome coupon a code and a discount", () => {
    const coupon = experimentsFor(site({ ...OPTIONS, welcome_popup: "none" })).find((x) => x.id === "coupon_popup");
    expect(coupon?.options).toMatchObject({ welcome_popup: "coupon", coupon_percent: 10, coupon_code: "WELCOME10" });
  });

  it("changes prices the way the store's currency rounds them, keeping the design", () => {
    const found = Object.fromEntries(experimentsFor(site()).map((x) => [x.id, x]));
    expect(found.prices_down?.options).toEqual(OPTIONS);
    expect(found.prices_down?.products?.map((p) => [p.price, p.list_price])[0]).toEqual([1169, 1599]);
    // A raised price that passes the old list price is no longer shown as a discount.
    expect(found.prices_up?.products?.map((p) => [p.price, p.list_price])).toEqual([
      [1429, 1599], [1099, 0], [495, 0], [2750, 0], [132, 0], [3300, 0]]);
    const deals = found.best_seller_deals?.products ?? [];
    expect(deals.filter((p, i) => p.price !== PRODUCTS[i]?.price).map((p) => p.id)).toEqual(["a", "b", "c", "d", "e"]);
    expect(deals[1]).toMatchObject({ price: 799, list_price: 999 });
    const won = experimentsFor(site(OPTIONS, "KRW", [product("k", 12900, 5)])).find((x) => x.id === "prices_down");
    expect(won?.products?.[0]?.price).toBe(11600);
    expect(experimentsFor(site(OPTIONS, "USD", [])).map((x) => x.id)).not.toContain("prices_down");
  });
});
