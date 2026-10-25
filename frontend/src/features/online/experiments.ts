// One-click design experiments: a change to a store's options that becomes a variant of it, compared with the store
// on the same shoppers. Each applies only when it would change something.

import type { PaymentMethod, SiteOptions } from "@/shared/api/online";
import type { MessageKey } from "@/shared/i18n/messages";

export interface QuickExperiment {
  id: string;
  label: MessageKey;
  change: (o: SiteOptions) => Partial<SiteOptions> | null;
}

const WALLETS: PaymentMethod[] = ["apple_pay", "bnpl"];

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
];

/** The experiments that would change this store, each with the variant's options. */
export function experimentsFor(options: SiteOptions): (QuickExperiment & { options: SiteOptions })[] {
  return QUICK_EXPERIMENTS.flatMap((x) => {
    const change = x.change(options);
    return change ? [{ ...x, options: { ...options, ...change } }] : [];
  });
}
