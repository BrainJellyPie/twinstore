// One-click experiments: a change to a store's design or prices that becomes a variant of it, compared with the store
// on the same shoppers. Each applies only when it would change something.

import type { OnlineProduct, OnlineSite, PaymentMethod, SiteOptions } from "@/shared/api/online";
import type { MessageKey } from "@/shared/i18n/messages";
import { minorUnitDivisor } from "@/shared/utils/money";

export interface QuickExperiment {
  id: string;
  label: MessageKey;
  change?: (o: SiteOptions) => Partial<SiteOptions> | null;
  reprice?: (products: OnlineProduct[], currency: string) => OnlineProduct[] | null;
}

const WALLETS: PaymentMethod[] = ["apple_pay", "bnpl"];
const BEST_SELLERS = 5;

/** A price times `factor`, rounded the way the store's prices are (cents, or 10 yen / 100 won steps). */
function scaled(price: number, factor: number, currency: string): number {
  const step = minorUnitDivisor(currency) === 100 ? 1 : currency === "KRW" ? 100 : 10;
  return Math.max(step, Math.round((price * factor) / step) * step);
}

function repriced(products: OnlineProduct[], factor: number, currency: string): OnlineProduct[] | null {
  if (!products.length) return null;
  return products.map((p) => {
    const price = scaled(p.price, factor, currency);
    return { ...p, price, list_price: p.list_price > price ? p.list_price : 0 };
  });
}

export const QUICK_EXPERIMENTS: QuickExperiment[] = [
  { id: "no_service_fee", label: "onXpNoServiceFee", change: (o) => (o.service_fee > 0 ? { service_fee: 0 } : null) },
  { id: "guest_checkout", label: "onXpGuest", change: (o) => (o.guest_checkout ? null : { guest_checkout: true }) },
  { id: "untick_addon", label: "onXpUntickAddon", change: (o) => (o.preselected_addon_percent > 0 ? { preselected_addon_percent: 0 } : null) },
  { id: "no_popup", label: "onXpNoPopup", change: (o) => (o.welcome_popup !== "none" ? { welcome_popup: "none" } : null) },
  {
    id: "coupon_popup", label: "onXpCouponPopup",
    change: (o) => (o.welcome_popup === "none"
      ? { welcome_popup: "coupon", coupon_percent: o.coupon_percent || 10, coupon_code: o.coupon_code || "WELCOME10" }
      : null),
  },
  { id: "faster", label: "onXpFaster", change: (o) => (o.page_load_ms >= 300 ? { page_load_ms: Math.round(o.page_load_ms / 2) } : null) },
  { id: "slower", label: "onXpSlower", change: (o) => (o.page_load_ms <= 7500 ? { page_load_ms: o.page_load_ms * 2 } : null) },
  { id: "free_delivery", label: "onXpFreeDelivery", change: (o) => (o.shipping_fee > 0 ? { shipping_fee: 0 } : null) },
  {
    id: "lower_threshold", label: "onXpLowerThreshold",
    change: (o) => (o.shipping_fee > 0 && o.free_shipping_threshold > 0
      ? { free_shipping_threshold: Math.round((o.free_shipping_threshold * 2) / 3) }
      : null),
  },
  { id: "smart_search", label: "onXpSmartSearch", change: (o) => (o.search !== "smart" ? { search: "smart" } : null) },
  { id: "one_page", label: "onXpOnePage", change: (o) => (o.checkout_flow === "multi_step" ? { checkout_flow: "one_page" } : null) },
  { id: "no_pressure", label: "onXpNoPressure", change: (o) => (o.urgency || o.social_proof ? { urgency: false, social_proof: false } : null) },
  { id: "pressure", label: "onXpPressure", change: (o) => (!o.urgency && !o.social_proof ? { urgency: true, social_proof: true } : null) },
  { id: "no_cookie_banner", label: "onXpNoCookie", change: (o) => (o.cookie_banner ? { cookie_banner: false } : null) },
  { id: "no_sponsored", label: "onXpNoSponsored", change: (o) => (o.sponsored_slots > 0 ? { sponsored_slots: 0 } : null) },
  {
    id: "wallets", label: "onXpWallets",
    change: (o) => {
      const missing = WALLETS.filter((m) => !o.payment_methods.includes(m));
      return missing.length ? { payment_methods: [...o.payment_methods, ...missing] } : null;
    },
  },
  { id: "cart_reminder", label: "onXpReminder", change: (o) => (o.cart_reminder ? null : { cart_reminder: true }) },
  {
    id: "reminder_discount", label: "onXpReminderDiscount",
    change: (o) => (o.cart_reminder_percent ? null : { cart_reminder: true, cart_reminder_percent: 10 }),
  },
  { id: "free_returns", label: "onXpFreeReturns", change: (o) => (o.return_policy !== "free_30" ? { return_policy: "free_30" } : null) },
  { id: "large_text", label: "onXpLargeText", change: (o) => (o.large_text ? null : { large_text: true }) },
  { id: "quick_add", label: "onXpQuickAdd", change: (o) => (o.quick_add ? null : { quick_add: true }) },
  { id: "prices_down", label: "onXpPricesDown", reprice: (products, currency) => repriced(products, 0.9, currency) },
  { id: "prices_up", label: "onXpPricesUp", reprice: (products, currency) => repriced(products, 1.1, currency) },
  {
    id: "best_seller_deals", label: "onXpBestSellerDeals",
    reprice: (products, currency) => {
      const top = new Set([...products].filter((p) => p.stock !== 0).sort((a, b) => b.weekly_sales - a.weekly_sales)
        .slice(0, BEST_SELLERS).map((p) => p.id));
      if (!top.size) return null;
      return products.map((p) => (top.has(p.id)
        ? { ...p, price: scaled(p.price, 0.8, currency), list_price: Math.max(p.list_price, p.price) }
        : p));
    },
  },
];

/** The experiments that would change this store, each with the variant's options and, for price tests, products. */
export function experimentsFor(site: OnlineSite): (QuickExperiment & { options: SiteOptions; products?: OnlineProduct[] })[] {
  return QUICK_EXPERIMENTS.flatMap((x) => {
    const change = x.change?.(site.options);
    if (change) return [{ ...x, options: { ...site.options, ...change } }];
    const products = x.reprice?.(site.products, site.currency);
    return products ? [{ ...x, options: site.options, products }] : [];
  });
}
