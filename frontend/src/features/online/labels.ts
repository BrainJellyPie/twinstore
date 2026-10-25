// Display names of the online-store codes the server sends. Codes stay unchanged; only these labels are translated.

import type {
  ActionKind, DeltaMetric, Device, FunnelStage, HomeSection, PageKind, PaymentMethod, SessionOutcome, ShopperMission,
  ShopperPolicyKind, SortKey, TemplateHighlight,
} from "@/shared/api/online";
import { messages, type MessageKey } from "@/shared/i18n/messages";

export const PAGE_LABELS: Record<PageKind, MessageKey> = {
  home: "onPageHome", category: "onPageCategory", search: "onPageSearch", deals: "onPageDeals", product: "onPageProduct",
  cart: "onPageCart", sign_in: "onPageSignIn", checkout: "onPageCheckout", order_complete: "onPageOrderComplete",
  wishlist: "onPageWishlist", help: "onPageHelp", settings: "onPageSettings",
};

export const ACTION_LABELS: Record<ActionKind, MessageKey> = {
  search: "onActSearch", back: "onActBack", home: "onActHome", open_category: "onActCategory", open_product: "onActProduct",
  open_deals: "onActDeals", open_menu: "onActMenu", close_menu: "onActCloseMenu", open_settings: "onActSettings",
  toggle_large_text: "onActLargeText", open_help: "onActHelp", open_cart: "onActCart", open_wishlist: "onActWishlist",
  add_to_cart: "onActAddToCart", buy_now: "onActBuyNow", add_to_wishlist: "onActSaveWishlist", read_reviews: "onActReviews",
  increase_quantity: "onActMore", remove_from_cart: "onActRemove", apply_coupon: "onActCoupon", checkout: "onActCheckout",
  sign_in: "onActSignIn", create_account: "onActCreateAccount", guest_checkout: "onActGuest", add_address: "onActAddress",
  add_payment: "onActPayment", remove_addon: "onActRemoveAddon", place_order: "onActPlaceOrder", sort: "onActSort",
  next_page: "onActNextPage", previous_page: "onActPreviousPage", close_popup: "onActClosePopup",
  accept_popup: "onActAcceptPopup", accept_cookies: "onActAcceptCookies", reject_cookies: "onActRejectCookies",
  leave: "onActLeave",
};

export const OUTCOME_LABELS: Record<SessionOutcome, MessageKey> = {
  purchased: "onOutPurchased", abandoned_cart: "onOutAbandoned", left: "onOutLeft", bounced: "onOutBounced",
  timed_out: "onOutTimedOut", step_limit: "onOutStepLimit",
};

export const OUTCOME_COLORS: Record<SessionOutcome, string> = {
  purchased: "bg-positive", abandoned_cart: "bg-amber-500", left: "bg-slate-400", bounced: "bg-negative",
  timed_out: "bg-violet-500", step_limit: "bg-sky-500",
};

export const MISSION_LABELS: Record<ShopperMission, MessageKey> = {
  purchase: "onMissionPurchase", browse: "onMissionBrowse", compare: "onMissionCompare", deal_hunt: "onMissionDeal",
  gift: "onMissionGift", replenish: "onMissionReplenish",
};

export const MISSION_HINTS: Record<ShopperMission, MessageKey> = {
  purchase: "onMissionPurchaseHint", browse: "onMissionBrowseHint", compare: "onMissionCompareHint",
  deal_hunt: "onMissionDealHint", gift: "onMissionGiftHint", replenish: "onMissionReplenishHint",
};

export const FUNNEL_LABELS: Record<FunnelStage, MessageKey> = {
  visit: "onFunnelVisit", product_view: "onFunnelProduct", add_to_cart: "onFunnelCart", checkout: "onFunnelCheckout",
  payment: "onFunnelPayment", purchase: "onFunnelPurchase",
};

export const DEVICE_LABELS: Record<Device, MessageKey> = { desktop: "onDeviceDesktop", mobile: "onDeviceMobile" };

export const POLICY_LABELS: Record<ShopperPolicyKind, MessageKey> = { rule: "onPolicyRule", vlm: "onPolicyVlm", text: "onPolicyText" };
export const POLICY_HINTS: Record<ShopperPolicyKind, MessageKey> = {
  rule: "onPolicyRuleHint", vlm: "onPolicyVlmHint", text: "onPolicyTextHint",
};

export const HIGHLIGHT_LABELS: Record<TemplateHighlight, MessageKey> = {
  mobile: "onHlMobile", quick_add: "onHlQuickAdd", one_click: "onHlOneClick", coupon_popup: "onHlCouponPopup",
  newsletter_popup: "onHlNewsletterPopup", urgency: "onHlUrgency", social_proof: "onHlSocialProof", sponsored: "onHlSponsored",
  addon: "onHlAddon", service_fee: "onHlServiceFee", account_required: "onHlAccountRequired",
  one_page_checkout: "onHlOnePage", bnpl: "onHlBnpl", cash_on_delivery: "onHlCod", paid_returns: "onHlPaidReturns",
  large_text: "onHlLargeText", free_delivery: "onHlFreeDelivery",
};

export const SORT_LABELS: Record<SortKey, MessageKey> = {
  featured: "onSortFeatured", price_asc: "onSortPriceAsc", price_desc: "onSortPriceDesc", rating: "onSortRating",
  newest: "onSortNewest",
};

export const PAYMENT_LABELS: Record<PaymentMethod, MessageKey> = {
  card: "onPayCard", paypal: "onPayPaypal", apple_pay: "onPayApple", bnpl: "onPayBnpl", bank_transfer: "onPayBank",
  cash_on_delivery: "onPayCod",
};

export const SECTION_LABELS: Record<HomeSection, MessageKey> = {
  categories: "onSecCategories", bestsellers: "onSecBestsellers", deals: "onSecDeals", new: "onSecNew",
  recommended: "onSecRecommended",
};

export const DELTA_LABELS: Record<DeltaMetric, MessageKey> = {
  conversion: "onKpiConversion", revenue_per_session: "onKpiRevenuePerSession", add_to_cart_rate: "onKpiAddToCart",
  steps: "onKpiSteps", seconds: "onKpiSeconds",
};

/** The translated description of a built-in template, or the server's text for any other. */
export function templateDescriptionKey(templateId: string): MessageKey | null {
  const key = `onTpl_${templateId}`;
  return key in messages ? (key as MessageKey) : null;
}
