import { describe, expect, it } from "vitest";

import type { SiteOptions } from "@/shared/api/online";
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
  page_load_ms: 800,
};

describe("quick experiments", () => {
  it("each changes the store it applies to, and has a label", () => {
    const found = experimentsFor(OPTIONS);
    expect(found.map((x) => x.id)).not.toContain("pressure"); // urgency is already on
    expect(found.map((x) => x.id)).not.toContain("coupon_popup"); // a welcome popup is already on
    for (const x of found) {
      expect(x.options).not.toEqual(OPTIONS);
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
      const once = x.change(OPTIONS);
      if (once && !steps.has(x.id)) expect(x.change({ ...OPTIONS, ...once })).toBeNull();
    }
    const tidy = { ...OPTIONS, service_fee: 0, guest_checkout: true, shipping_fee: 0, page_load_ms: 200 };
    const ids = experimentsFor(tidy).map((x) => x.id);
    for (const id of ["no_service_fee", "guest_checkout", "free_delivery", "lower_threshold", "faster"]) expect(ids).not.toContain(id);
  });

  it("gives a welcome coupon a code and a discount", () => {
    const coupon = experimentsFor({ ...OPTIONS, welcome_popup: "none" }).find((x) => x.id === "coupon_popup");
    expect(coupon?.options).toMatchObject({ welcome_popup: "coupon", coupon_percent: 10, coupon_code: "WELCOME10" });
  });
});
