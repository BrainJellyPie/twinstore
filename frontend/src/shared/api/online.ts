// Online stores API: template web shops, sites and variants, browsing as a shopper, and runs of virtual online
// shoppers. Mirrors backend domain/online.py and application/online.py — keep in sync. Prices are integers in the
// currency's minor unit.

import { BASE, type EnsembleConfig } from "./client";
import { apiErrorMessage } from "./errors";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(apiErrorMessage(body, `${res.status} ${res.statusText}`));
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

export type PageKind =
  | "home" | "category" | "search" | "deals" | "product" | "cart" | "sign_in" | "checkout" | "order_complete"
  | "wishlist" | "help" | "settings";
export type ActionKind =
  | "search" | "back" | "home" | "open_category" | "open_product" | "open_deals" | "open_menu" | "close_menu"
  | "open_settings" | "toggle_large_text" | "open_help" | "open_cart" | "open_wishlist" | "add_to_cart" | "buy_now"
  | "add_to_wishlist" | "read_reviews" | "increase_quantity" | "remove_from_cart" | "apply_coupon" | "checkout"
  | "sign_in" | "create_account" | "guest_checkout" | "add_address" | "add_payment" | "remove_addon" | "place_order"
  | "sort" | "next_page" | "previous_page" | "close_popup" | "accept_popup" | "accept_cookies" | "reject_cookies"
  | "leave";
export type SortKey = "featured" | "price_asc" | "price_desc" | "rating" | "newest";
export type Device = "desktop" | "mobile";
export type PaymentMethod = "card" | "paypal" | "apple_pay" | "bnpl" | "bank_transfer" | "cash_on_delivery";
export type HomeSection = "categories" | "bestsellers" | "deals" | "new" | "recommended";
export type ShopperMission = "purchase" | "browse" | "compare" | "deal_hunt" | "gift" | "replenish";
export type ShopperPolicyKind = "rule" | "vlm" | "text";
export type SessionOutcome = "purchased" | "abandoned_cart" | "left" | "bounced" | "timed_out" | "step_limit";
export type FunnelStage = "visit" | "product_view" | "add_to_cart" | "checkout" | "payment" | "purchase";
export type ProductBadge = "bestseller" | "new" | "limited" | "eco" | "sponsored";
export type Vision = "typical" | "low_vision" | "color_blind" | "aging_eyes";
export type AdPlacement = "hero_banner" | "sponsored_listing" | "home_tile" | "product_page" | "cart_upsell" | "popup";
export type Accessibility = "typical" | "realistic" | "low_vision" | "color_blind" | "aging_eyes";
export type FrictionCode =
  | "popup_shown" | "popup_left" | "popup_accepted" | "signin_reached" | "signin_left" | "account_created" | "fee_seen"
  | "fee_left" | "addon_seen" | "addon_removed" | "addon_paid" | "coupon_failed" | "zero_results" | "sold_out_seen"
  | "slow_exit" | "cookies_rejected";
export type TemplateHighlight =
  | "mobile" | "quick_add" | "one_click" | "coupon_popup" | "newsletter_popup" | "urgency" | "social_proof"
  | "sponsored" | "addon" | "service_fee" | "account_required" | "one_page_checkout" | "bnpl" | "cash_on_delivery"
  | "paid_returns" | "large_text" | "free_delivery";

export const MISSIONS: ShopperMission[] = ["purchase", "browse", "compare", "deal_hunt", "gift", "replenish"];
export const VISIONS: Vision[] = ["typical", "low_vision", "color_blind", "aging_eyes"];
export const AD_PLACEMENTS: AdPlacement[] = ["hero_banner", "sponsored_listing", "home_tile", "product_page", "cart_upsell", "popup"];
export const ACCESSIBILITY: Accessibility[] = ["typical", "realistic", "low_vision", "color_blind", "aging_eyes"];
export const PAYMENT_METHODS: PaymentMethod[] = ["card", "paypal", "apple_pay", "bnpl", "bank_transfer", "cash_on_delivery"];
export const HOME_SECTIONS: HomeSection[] = ["categories", "bestsellers", "deals", "new", "recommended"];
export const FROM_STORE = "from_store";

export interface OnlineTemplate {
  id: string; name: string; vertical: string; tagline: string; description: string;
  categories: number; products: number; photos: number; theme_color: string; highlights: TemplateHighlight[];
}

export interface OnlineCategory { id: string; name: string; glyph: string }

export interface OnlineProduct {
  id: string; name: string; category_id: string; price: number; list_price: number; rating: number; reviews: number;
  badges: ProductBadge[]; stock: number | null; description: string; tags: string[]; image_url: string;
  weekly_sales: number; sku: string;
}

export interface SiteOptions {
  theme_color: string; device: Device | null; grid_columns: number; products_per_page: number; hero_banner: boolean;
  hero_text: string; home_sections: HomeSection[]; large_text: boolean; show_ratings: boolean; show_review_counts: boolean;
  default_sort: SortKey; search: "smart" | "exact" | "off"; sponsored_slots: number;
  recommendations: "none" | "popular" | "similar"; quick_add: boolean; reviews_on_product: boolean; wishlist: boolean;
  urgency: boolean; social_proof: boolean; welcome_popup: "none" | "newsletter" | "coupon"; cookie_banner: boolean;
  chat_widget: boolean; shipping_fee: number; free_shipping_threshold: number; coupon_code: string;
  coupon_percent: number; coupon_public: boolean; guest_checkout: boolean; checkout_flow: "one_page" | "multi_step";
  payment_methods: PaymentMethod[]; one_click_buy: boolean; service_fee: number; preselected_addon_percent: number;
  return_policy: "free_30" | "paid" | "hidden"; trust_badges: boolean; page_load_ms: number;
  cart_reminder: boolean; cart_reminder_percent: number;
}

export interface AdCampaign {
  id: string; name: string; product_id: string; placement: AdPlacement; headline: string; pricing: "cpc" | "cpm";
  cost: number; active: boolean;
}

export interface OnlineSite {
  id: string; name: string; template_id: string; currency: string; tagline: string;
  categories: OnlineCategory[]; products: OnlineProduct[]; options: SiteOptions; ads: AdCampaign[];
  variant_of: string; note: string; created_at: string; updated_at: string;
}

export interface SiteSummary {
  id: string; name: string; template_id: string; currency: string; categories: number; products: number;
  photos: number; theme_color: string; device: Device | null; variant_of: string; note: string;
  created_at: string; updated_at: string;
}

export interface PageRef {
  page: PageKind; category_id: string; query: string; product_id: string; sort: SortKey | null; page_index: number;
  checkout_step: "address" | "payment" | "review";
}

export interface BrowserState {
  at: PageRef; history: PageRef[]; overlay: "none" | "menu" | "welcome" | "promo"; cart: { product_id: string; quantity: number }[];
  wishlist: string[]; viewed: string[]; reviews_open: boolean; welcome_seen: boolean; cookies_answered: boolean;
  coupon_known: boolean; coupon_applied: boolean; signed_in: boolean; guest: boolean; address_added: boolean;
  payment_method: PaymentMethod | null; addon_removed: boolean; large_text: boolean; text_size_changed?: boolean;
  device: Device; reminder_percent?: number; notice: string;
  order_id: string; order: { product_id: string; quantity: number }[]; order_total: number;
}

export interface PageOption {
  kind: ActionKind; target: string; label: string; number: number; box: [number, number, number, number] | null;
  ad_id: string;
}

export interface PageView {
  url: string; title: string; page: PageKind; options: PageOption[]; outline: string[]; state: BrowserState;
  image: string; width: number; height: number;
}

export interface OnlineShopper {
  id: string; identity: string; age_group: string; gender: string; device: Device; mission: ShopperMission; goal: string;
  target_category: string; target_terms: string[]; target_product: string; budget: number; price_sensitivity: number;
  patience_sec: number; tech_savvy: number; has_account: boolean; description: string; persona_id: string;
  vision: Vision;
}

export interface ExitSurvey {
  satisfaction: number; ease: number; recommend: number; would_return: boolean; frustration: string; improvement: string;
}

export interface SessionStep {
  index: number; url: string; page: PageKind; state: BrowserState; options: number; choice: PageOption | null;
  search_text: string; thought: string; seconds: number; load_seconds: number; source: "rule" | "model" | "fallback";
  error: string; mark_seed: number; screen: [number, number] | null; ads: string[];
}

export interface SessionResult {
  shopper_id: string; site_id: string; outcome: SessionOutcome; steps: SessionStep[];
  order: { product_id: string; name: string; category_id: string; quantity: number; price: number }[];
  subtotal: number; order_total: number; seconds: number; reached: FunnelStage[]; viewed_products: string[];
  searches: { query: string; results: number; step: number }[]; exit_page: PageKind; exit_thought: string;
  model_requests: number; fallbacks: number; survey: ExitSurvey | null; addon_paid: number; discount: number;
  reminded: boolean; returned_at: number | null;
}

export interface OnlineRunRequest {
  site_ids: string[]; name?: string; shoppers: number; policy: ShopperPolicyKind; model?: string | null;
  ensemble?: EnsembleConfig | null; seed: number; max_steps: number; missions: Record<ShopperMission, number>;
  mobile_share: number; source: "panel" | "project"; image_width: number; shuffle_marks: boolean;
  accessibility: Accessibility; exit_survey: boolean;
}

export interface FunnelRow { stage: FunnelStage; sessions: number; share: number }
export type SegmentDimension = "mission" | "device" | "age_group" | "gender" | "vision";
export interface SegmentRow {
  dimension: SegmentDimension; value: string; sessions: number; conversion: number;
  revenue_per_session: number; avg_steps: number;
}
export interface ProductRow { product_id: string; name: string; views: number; adds: number; purchases: number; units: number; revenue: number }
export interface SearchTermRow { query: string; count: number; zero_results: number; purchases: number }
export interface ClickPoint { page: PageKind; kind: ActionKind; device: Device; x: number; y: number }

export interface FrictionRow { code: FrictionCode; sessions: number; share: number; amount: number }
export interface AdRow {
  ad_id: string; name: string; placement: AdPlacement; product_id: string; product_name: string; impressions: number;
  reach: number; clicks: number; ctr: number; click_conversions: number; view_conversions: number;
  attributed_revenue: number; units_sold: number; cost: number; roas: number | null;
}
export interface AdLift {
  ad_id: string; name: string; site_id: string; product_id: string; units_without: number; units_with: number; units_diff: number;
  revenue_diff: number; other_revenue_diff: number; cost: number; iroas: number | null;
}
export interface SurveySummary {
  responses: number; satisfaction: number; ease: number; nps: number; would_return: number; frustrations: string[];
  improvements: string[];
}

export interface RecoveryRow { emails: number; returned: number; recovered: number; revenue: number; discount: number }

export interface VariantSummary {
  site_id: string; site_name: string; sessions: number; purchases: number; conversion: number; revenue: number;
  aov: number; revenue_per_session: number; bounce_rate: number; cart_abandonment: number; add_to_cart_rate: number;
  avg_steps: number; avg_seconds: number; search_share: number; zero_result_searches: number;
  outcomes: Partial<Record<SessionOutcome, number>>; actions: Partial<Record<ActionKind, number>>;
  funnel: FunnelRow[]; exits: { page: PageKind; sessions: number }[]; segments: SegmentRow[]; products: ProductRow[];
  searches: SearchTermRow[]; clicks: ClickPoint[]; frictions: FrictionRow[]; survey: SurveySummary | null; ads: AdRow[];
  recovery: RecoveryRow | null;
}

export type DeltaMetric = "conversion" | "revenue_per_session" | "add_to_cart_rate" | "steps" | "seconds" | "satisfaction" | "recommend";
export interface PairedDelta {
  metric: DeltaMetric; control: number; variant: number; diff: number; ci_low: number | null; ci_high: number | null; n: number;
}

/** Variant minus control within one segment of the same shoppers. */
export interface SegmentDelta {
  dimension: SegmentDimension; value: string; n: number; control_conversion: number; variant_conversion: number;
  conversion_diff: number; ci_low: number | null; ci_high: number | null; revenue_diff: number;
}
/** A shopper whose visit ended differently in the two stores. */
export interface SwitchRow {
  shopper_id: string; control_outcome: SessionOutcome; variant_outcome: SessionOutcome; control_total: number;
  variant_total: number; control_exit: PageKind; variant_exit: PageKind; control_thought: string; variant_thought: string;
}

export interface OnlineRunResult {
  run_id: string; name: string; policy: ShopperPolicyKind; model: string; currency: string;
  variants: VariantSummary[];
  comparisons: {
    site_id: string; site_name: string; deltas: PairedDelta[]; ad_lifts: AdLift[]; segments: SegmentDelta[]; won: number;
    lost: number; changed: number; switches: SwitchRow[];
  }[];
  shoppers: OnlineShopper[]; model_requests: number; fallbacks: number; seconds: number; notes: string[];
}

export interface OnlineRunStatus {
  run_id: string; name: string; site_ids: string[]; site_names: string[];
  status: "pending" | "running" | "completed" | "failed"; phase: string; done: number; total: number; error: string;
  request: OnlineRunRequest; created_at: string; finished_at: string;
}

export interface OnlineRunView { status: OnlineRunStatus; result: OnlineRunResult | null }
export interface SessionView { variant: number; site_id: string; site_name: string; shopper: OnlineShopper; session: SessionResult }

export const onlineKeys = {
  templates: () => ["online", "templates"] as const,
  sites: (pid: string) => ["projects", pid, "online", "sites"] as const,
  site: (pid: string, siteId: string) => ["projects", pid, "online", "sites", siteId] as const,
  runs: (pid: string) => ["projects", pid, "online", "runs"] as const,
  run: (pid: string, runId: string) => ["projects", pid, "online", "runs", runId] as const,
  session: (pid: string, runId: string, variant: number, shopperId: string) =>
    ["projects", pid, "online", "runs", runId, "sessions", variant, shopperId] as const,
};

export function listTemplates(signal?: AbortSignal): Promise<OnlineTemplate[]> {
  return fetchJson("/api/online/templates", { signal });
}

export function templatePreviewUrl(templateId: string, currency: string): string {
  return `${BASE}/api/online/templates/${encodeURIComponent(templateId)}/preview.png?currency=${encodeURIComponent(currency)}`;
}

export function listSites(pid: string, signal?: AbortSignal): Promise<SiteSummary[]> {
  return fetchJson(`/api/projects/${pid}/online/sites`, { signal });
}

export function createSite(pid: string, body: { template_id: string; name?: string; seed?: number; setup_id?: string | null }): Promise<OnlineSite> {
  return fetchJson(`/api/projects/${pid}/online/sites`, { method: "POST", ...json(body) });
}

export function getSite(pid: string, siteId: string, signal?: AbortSignal): Promise<OnlineSite> {
  return fetchJson(`/api/projects/${pid}/online/sites/${siteId}`, { signal });
}

export function saveSite(pid: string, site: OnlineSite): Promise<OnlineSite> {
  return fetchJson(`/api/projects/${pid}/online/sites/${site.id}`, { method: "PUT", ...json(site) });
}

export function copySite(pid: string, siteId: string, body: {
  name?: string; note?: string; options?: SiteOptions | null; products?: OnlineProduct[] | null; ads?: AdCampaign[] | null;
}): Promise<OnlineSite> {
  return fetchJson(`/api/projects/${pid}/online/sites/${siteId}/copy`, { method: "POST", ...json(body) });
}

export function deleteSite(pid: string, siteId: string): Promise<{ status: string }> {
  return fetchJson(`/api/projects/${pid}/online/sites/${siteId}`, { method: "DELETE" });
}

export function sitePreviewUrl(pid: string, siteId: string, device: Device, version: string): string {
  return `${BASE}/api/projects/${pid}/online/sites/${siteId}/preview.png?device=${device}&v=${encodeURIComponent(version)}`;
}

export function browse(
  pid: string, siteId: string,
  body: {
    state?: BrowserState | null; option?: number | null; query?: string; mark_seed?: number; has_account?: boolean;
    device?: Device; vision?: Vision;
  },
  signal?: AbortSignal,
): Promise<PageView> {
  return fetchJson(`/api/projects/${pid}/online/sites/${siteId}/browse`, { method: "POST", ...json(body), signal });
}

export function startRun(pid: string, body: OnlineRunRequest): Promise<OnlineRunStatus> {
  return fetchJson(`/api/projects/${pid}/online/runs`, { method: "POST", ...json(body) });
}

export function listRuns(pid: string, signal?: AbortSignal): Promise<OnlineRunStatus[]> {
  return fetchJson(`/api/projects/${pid}/online/runs`, { signal });
}

export function getRun(pid: string, runId: string, signal?: AbortSignal): Promise<OnlineRunView> {
  return fetchJson(`/api/projects/${pid}/online/runs/${runId}`, { signal });
}

export function deleteRun(pid: string, runId: string): Promise<{ status: string }> {
  return fetchJson(`/api/projects/${pid}/online/runs/${runId}`, { method: "DELETE" });
}

export function getSession(pid: string, runId: string, variant: number, shopperId: string, signal?: AbortSignal): Promise<SessionView> {
  return fetchJson(`/api/projects/${pid}/online/runs/${runId}/sessions/${variant}/${shopperId}`, { signal });
}

export function stepScreenshotUrl(pid: string, runId: string, variant: number, shopperId: string, step: number): string {
  return `${BASE}/api/projects/${pid}/online/runs/${runId}/sessions/${variant}/${shopperId}/steps/${step}.png`;
}

export function clickstreamUrl(pid: string, runId: string): string {
  return `${BASE}/api/projects/${pid}/online/runs/${runId}/clickstream.csv`;
}
