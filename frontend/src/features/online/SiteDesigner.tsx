// Design an online store: its look, catalog, persuasion and checkout choices, prices and stock. Save the store, or
// save the changes as a variant to compare with the original on the same virtual shoppers.

import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Loader2, Save, Trash2 } from "lucide-react";

import {
  copySite, deleteSite, getSite, HOME_SECTIONS, onlineKeys, PAYMENT_METHODS, saveSite,
  type AdCampaign, type OnlineProduct, type OnlineSite, type SiteOptions,
} from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { majorUnitText, minorUnitDivisor, toMinor } from "@/shared/utils/money";
import { searchText } from "@/shared/utils/searchText";

import { AdsEditor } from "./AdsEditor";
import { PAYMENT_LABELS, SECTION_LABELS, SORT_LABELS } from "./labels";
import { StylePicker } from "./StylePicker";

const PRODUCT_ROWS = 60;

export function SiteDesigner({ projectId, siteId, onCopied, onDeleted }: {
  projectId: string; siteId: string; onCopied: (siteId: string) => void; onDeleted: () => void;
}) {
  const { t } = useI18n();
  const site = useQuery({ queryKey: onlineKeys.site(projectId, siteId), queryFn: ({ signal }) => getSite(projectId, siteId, signal) });
  if (site.isPending) return <div className="panel rounded-[1.6rem] p-4 text-sm text-muted-foreground">{t("studioLoading")}</div>;
  if (site.isError) return <div role="alert" className="panel rounded-[1.6rem] p-4 text-sm text-destructive">{site.error.message}</div>;
  return <Designer key={site.data.updated_at} projectId={projectId} site={site.data} onCopied={onCopied} onDeleted={onDeleted} />;
}

function Designer({ projectId, site, onCopied, onDeleted }: {
  projectId: string; site: OnlineSite; onCopied: (siteId: string) => void; onDeleted: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [name, setName] = useState(site.name);
  const [note, setNote] = useState(site.note);
  const [options, setOptions] = useState<SiteOptions>(site.options);
  const [products, setProducts] = useState<OnlineProduct[]>(site.products);
  const [ads, setAds] = useState<AdCampaign[]>(site.ads);
  const [amountDrafts, setAmountDrafts] = useState<Record<string, string>>({});
  const [filter, setFilter] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const invalidAmounts = Object.values(amountDrafts).some((text) => toMinor(text, minorUnitDivisor(site.currency)) === null);
  const editAmount = (field: string, text: string) => setAmountDrafts((drafts) => ({ ...drafts, [field]: text }));
  // A removed ad takes its unfinished cost text with it.
  const changeAds = (next: AdCampaign[]) => {
    setAds(next);
    setAmountDrafts((drafts) => Object.fromEntries(Object.entries(drafts).filter(
      ([field]) => !field.startsWith("ad_cost:") || next.some((ad) => field === `ad_cost:${ad.id}`))));
  };
  const set = <K extends keyof SiteOptions>(key: K, value: SiteOptions[K]) => setOptions((o) => ({ ...o, [key]: value }));
  const draft: OnlineSite = { ...site, name: name.trim() || site.name, note, options, products, ads };
  const refresh = () => Promise.all([
    qc.invalidateQueries({ queryKey: onlineKeys.sites(projectId), exact: true }),
    qc.invalidateQueries({ queryKey: onlineKeys.site(projectId, site.id), exact: true }),
  ]);
  const save = useMutation({ mutationFn: () => saveSite(projectId, draft), onSuccess: refresh });
  const variant = useMutation({
    mutationFn: () => copySite(projectId, site.id, {
      name: name.trim() && name.trim() !== site.name ? name.trim() : undefined, note, options,
      products: products === site.products ? undefined : products,
      ads: ads === site.ads ? undefined : ads,
    }),
    onSuccess: async (copy) => { await refresh(); onCopied(copy.id); },
  });
  const withoutAds = useMutation({
    // This store is saved first, so the copy differs from it only in its ads.
    mutationFn: async () => {
      await saveSite(projectId, draft);
      return copySite(projectId, site.id, {
        name: t("onNoAdsName", { name: draft.name }).slice(0, 60), note: t("onNoAdsNote"),
        ads: ads.map((ad) => ({ ...ad, active: false })),
      });
    },
    onSuccess: async (copy) => { await refresh(); onCopied(copy.id); },
  });
  const remove = useMutation({
    mutationFn: () => deleteSite(projectId, site.id),
    onSuccess: () => {
      // Drop the deleted store's own query rather than refetching it into a 404; only the list changes.
      onDeleted();
      qc.removeQueries({ queryKey: onlineKeys.site(projectId, site.id), exact: true });
      void qc.invalidateQueries({ queryKey: onlineKeys.sites(projectId), exact: true });
    },
  });
  const error = save.error ?? variant.error ?? remove.error ?? withoutAds.error;
  const writing = save.isPending || variant.isPending || remove.isPending || withoutAds.isPending;

  const shown = useMemo(() => {
    const words = searchText(filter);
    return products.filter((p) => !words || searchText(p.name).includes(words)).slice(0, PRODUCT_ROWS);
  }, [products, filter]);
  const updateProduct = (id: string, change: Partial<OnlineProduct>) =>
    setProducts((all) => all.map((p) => (p.id === id ? { ...p, ...change } : p)));
  const toggle = (key: keyof SiteOptions, label: MessageKey, hint?: MessageKey) => (
    <Toggle label={t(label)} hint={hint && t(hint)} checked={options[key] as boolean} onChange={(v) => set(key, v as never)} />
  );

  return (
    <fieldset disabled={writing} className="grid min-w-0 gap-3 xl:grid-cols-2">
      <Card title={t("onDesignStore")}>
        <Field label={t("onStoreName")}><Input aria-label={t("onStoreName")} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label={t("onVariantNote")} hint={t("onVariantNoteHint")}>
          <Input aria-label={t("onVariantNote")} value={note} maxLength={400} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button onClick={() => save.mutate()} disabled={save.isPending || invalidAmounts}>
            {save.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />} {t("onSave")}
          </Button>
          <Button variant="outline" onClick={() => variant.mutate()} disabled={variant.isPending || invalidAmounts} title={t("onSaveVariantHint")}>
            {variant.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Copy className="size-4" aria-hidden />} {t("onSaveVariant")}
          </Button>
          {confirmDelete ? (
            <Button variant="destructive" onClick={() => remove.mutate()} disabled={remove.isPending}>{t("onConfirmDelete")}</Button>
          ) : (
            <Button variant="ghost" onClick={() => setConfirmDelete(true)}><Trash2 className="size-4" aria-hidden /> {t("studioDelete")}</Button>
          )}
        </div>
        {save.isSuccess && !save.isPending && <p role="status" className="text-xs text-positive">{t("studioSaved")}</p>}
        {error && <p role="alert" className="text-xs text-destructive">{error.message}</p>}
      </Card>

      <Card title={t("onStyleTitle")} hint={t("onStyleHint")} className="xl:col-span-2">
        <StylePicker projectId={projectId} siteId={site.id} storeName={site.name} version={site.updated_at}
          saved={site.options.page_style} value={options.page_style} onChange={(style) => set("page_style", style)} />
      </Card>

      <Card title={t("onDesignLook")}>
        <Field label={t("onOptTheme")}>
          <input type="color" value={options.theme_color} onChange={(e) => set("theme_color", e.target.value)} className="h-9 w-16 rounded border" aria-label={t("onOptTheme")} />
        </Field>
        <Field label={t("onOptDevice")} hint={t("onOptDeviceHint")}>
          <Select label={t("onOptDevice")} value={options.device ?? ""} onChange={(v) => set("device", v === "desktop" || v === "mobile" ? v : null)}
            choices={[["", t("onOptDeviceEach")], ["desktop", t("onDeviceDesktop")], ["mobile", t("onDeviceMobile")]]} />
        </Field>
        <Field label={t("onOptColumns")}><NumberInput label={t("onOptColumns")} value={options.grid_columns} min={2} max={5} onChange={(v) => set("grid_columns", v)} /></Field>
        <Field label={t("onOptPerPage")}><NumberInput label={t("onOptPerPage")} value={options.products_per_page} min={4} max={24} onChange={(v) => set("products_per_page", v)} /></Field>
        {toggle("hero_banner", "onOptHero")}
        <Field label={t("onOptHeroText")}><Input aria-label={t("onOptHeroText")} value={options.hero_text} maxLength={80} onChange={(e) => set("hero_text", e.target.value)} /></Field>
        <Field label={t("onOptSections")} hint={t("onOptSectionsHint")}>
          <div className="flex flex-wrap gap-2">
            {HOME_SECTIONS.map((section) => (
              <label key={section} className="flex items-center gap-1 text-xs">
                <input type="checkbox" checked={options.home_sections.includes(section)}
                  onChange={(e) => set("home_sections", e.target.checked ? [...options.home_sections, section] : options.home_sections.filter((s) => s !== section))} />
                {t(SECTION_LABELS[section])}
              </label>
            ))}
          </div>
        </Field>
        {toggle("large_text", "onOptLargeText", "onOptLargeTextHint")}
        <Field label={t("onOptLoad")} hint={t("onOptLoadHint")}>
          <div className="flex items-center gap-2">
            <input type="range" min={50} max={15000} step={50} value={options.page_load_ms} onChange={(e) => set("page_load_ms", Number(e.target.value))} className="flex-1" aria-label={t("onOptLoad")} />
            <span className="w-16 text-right text-xs tabular-nums">{(options.page_load_ms / 1000).toFixed(1)} s</span>
          </div>
        </Field>
      </Card>

      <Card title={t("onDesignCatalog")}>
        {toggle("show_ratings", "onOptRatings")}
        {toggle("show_review_counts", "onOptReviewCounts")}
        <Field label={t("onOptSort")}>
          <Select label={t("onOptSort")} value={options.default_sort} onChange={(v) => set("default_sort", v as SiteOptions["default_sort"])}
            choices={(Object.keys(SORT_LABELS) as SiteOptions["default_sort"][]).map((k) => [k, t(SORT_LABELS[k])])} />
        </Field>
        <Field label={t("onOptSearch")} hint={t("onOptSearchHint")}>
          <Select label={t("onOptSearch")} value={options.search} onChange={(v) => set("search", v as SiteOptions["search"])}
            choices={[["smart", t("onOptSearchSmart")], ["exact", t("onOptSearchExact")], ["off", t("onOptSearchOff")]]} />
        </Field>
        <Field label={t("onOptSponsored")} hint={t("onOptSponsoredHint")}>
          <NumberInput label={t("onOptSponsored")} value={options.sponsored_slots} min={0} max={4} onChange={(v) => set("sponsored_slots", v)} />
        </Field>
        <Field label={t("onOptRecs")}>
          <Select label={t("onOptRecs")} value={options.recommendations} onChange={(v) => set("recommendations", v as SiteOptions["recommendations"])}
            choices={[["none", t("onOptRecsNone")], ["popular", t("onOptRecsPopular")], ["similar", t("onOptRecsSimilar")]]} />
        </Field>
        {toggle("quick_add", "onOptQuickAdd", "onOptQuickAddHint")}
        {toggle("reviews_on_product", "onOptReviews")}
        {toggle("wishlist", "onOptWishlist")}
      </Card>

      <Card title={t("onDesignPersuasion")} hint={t("onDesignPersuasionHint")}>
        {toggle("urgency", "onOptUrgency", "onOptUrgencyHint")}
        {toggle("social_proof", "onOptSocial", "onOptSocialHint")}
        <Field label={t("onOptPopup")}>
          <Select label={t("onOptPopup")} value={options.welcome_popup} onChange={(v) => set("welcome_popup", v as SiteOptions["welcome_popup"])}
            choices={[["none", t("onOptPopupNone")], ["newsletter", t("onOptPopupNewsletter")], ["coupon", t("onOptPopupCoupon")]]} />
        </Field>
        {toggle("cookie_banner", "onOptCookies")}
        {toggle("chat_widget", "onOptChat")}
        {toggle("trust_badges", "onOptTrust")}
      </Card>

      <Card title={t("onDesignCheckout")}>
        <Field label={t("onOptShipping")}><Money label={t("onOptShipping")} value={options.shipping_fee} currency={site.currency}
          text={amountDrafts.shipping_fee} onTextChange={(text) => editAmount("shipping_fee", text)} onChange={(v) => set("shipping_fee", v)} /></Field>
        <Field label={t("onOptFreeOver")} hint={t("onOptFreeOverHint")}>
          <Money label={t("onOptFreeOver")} value={options.free_shipping_threshold} currency={site.currency}
            text={amountDrafts.free_shipping_threshold} onTextChange={(text) => editAmount("free_shipping_threshold", text)} onChange={(v) => set("free_shipping_threshold", v)} />
        </Field>
        <Field label={t("onOptCouponCode")}><Input aria-label={t("onOptCouponCode")} value={options.coupon_code} maxLength={20} onChange={(e) => set("coupon_code", e.target.value.toUpperCase())} /></Field>
        <Field label={t("onOptCouponPercent")}><NumberInput label={t("onOptCouponPercent")} value={options.coupon_percent} min={0} max={90} onChange={(v) => set("coupon_percent", v)} /></Field>
        {toggle("coupon_public", "onOptCouponPublic", "onOptCouponPublicHint")}
        {toggle("cart_reminder", "onOptReminder", "onOptReminderHint")}
        {options.cart_reminder && (
          <Field label={t("onOptReminderPercent")} hint={t("onOptReminderPercentHint")}>
            <NumberInput label={t("onOptReminderPercent")} value={options.cart_reminder_percent} min={0} max={50}
              onChange={(v) => set("cart_reminder_percent", v)} />
          </Field>
        )}
        {toggle("guest_checkout", "onOptGuest", "onOptGuestHint")}
        <Field label={t("onOptFlow")}>
          <Select label={t("onOptFlow")} value={options.checkout_flow} onChange={(v) => set("checkout_flow", v as SiteOptions["checkout_flow"])}
            choices={[["multi_step", t("onOptFlowMulti")], ["one_page", t("onOptFlowOne")]]} />
        </Field>
        <Field label={t("onOptPayments")}>
          <div className="flex flex-wrap gap-2">
            {PAYMENT_METHODS.map((m) => (
              <label key={m} className="flex items-center gap-1 text-xs">
                <input type="checkbox" checked={options.payment_methods.includes(m)}
                  onChange={(e) => set("payment_methods", e.target.checked ? [...options.payment_methods, m] : options.payment_methods.filter((x) => x !== m))} />
                {t(PAYMENT_LABELS[m])}
              </label>
            ))}
          </div>
        </Field>
        {toggle("one_click_buy", "onOptOneClick")}
        <Field label={t("onOptServiceFee")} hint={t("onOptServiceFeeHint")}>
          <Money label={t("onOptServiceFee")} value={options.service_fee} currency={site.currency}
            text={amountDrafts.service_fee} onTextChange={(text) => editAmount("service_fee", text)} onChange={(v) => set("service_fee", v)} />
        </Field>
        <Field label={t("onOptAddon")} hint={t("onOptAddonHint")}>
          <NumberInput label={t("onOptAddon")} value={options.preselected_addon_percent} min={0} max={50} onChange={(v) => set("preselected_addon_percent", v)} />
        </Field>
        <Field label={t("onOptReturns")}>
          <Select label={t("onOptReturns")} value={options.return_policy} onChange={(v) => set("return_policy", v as SiteOptions["return_policy"])}
            choices={[["free_30", t("onOptReturnsFree")], ["paid", t("onOptReturnsPaid")], ["hidden", t("onOptReturnsHidden")]]} />
        </Field>
      </Card>

      <Card title={t("onDesignAds")} hint={t("onDesignAdsHint")} className="xl:col-span-2">
        <AdsEditor ads={ads} products={products} currency={site.currency} onChange={changeAds}
          costText={(id) => amountDrafts[`ad_cost:${id}`]} onCostText={(id, text) => editAmount(`ad_cost:${id}`, text)}
          onCompareWithout={withoutAds.isPending || invalidAmounts ? undefined : () => withoutAds.mutate()} />
      </Card>

      <Card title={t("onDesignProducts", { count: products.length })} className="xl:col-span-2">
        <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t("onProductFilter")} aria-label={t("onProductFilter")} />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-xs">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-1 pr-2 font-medium">{t("onColProduct")}</th>
                <th className="py-1 pr-2 font-medium">{t("onColCategory")}</th>
                <th className="py-1 pr-2 font-medium">{t("onColPrice")}</th>
                <th className="py-1 pr-2 font-medium">{t("onColListPrice")}</th>
                <th className="py-1 pr-2 font-medium">{t("onColStock")}</th>
                <th className="py-1 pr-2 font-medium">{t("onColSponsored")}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="py-1 pr-2"><Input className="h-8" value={p.name} maxLength={120} onChange={(e) => updateProduct(p.id, { name: e.target.value })} aria-label={t("onColProduct")} /></td>
                  <td className="py-1 pr-2 text-muted-foreground">{site.categories.find((c) => c.id === p.category_id)?.name ?? p.category_id}</td>
                  <td className="py-1 pr-2"><Money label={`${p.name}: ${t("onColPrice")}`} value={p.price} currency={site.currency}
                    text={amountDrafts[`price:${p.id}`]} onTextChange={(text) => editAmount(`price:${p.id}`, text)} onChange={(v) => updateProduct(p.id, { price: v })} /></td>
                  <td className="py-1 pr-2"><Money label={`${p.name}: ${t("onColListPrice")}`} value={p.list_price} currency={site.currency}
                    text={amountDrafts[`list_price:${p.id}`]} onTextChange={(text) => editAmount(`list_price:${p.id}`, text)} onChange={(v) => updateProduct(p.id, { list_price: v })} /></td>
                  <td className="py-1 pr-2">
                    <Input className="h-8 w-20" inputMode="numeric" value={p.stock ?? ""} placeholder={t("onStockPlenty")} aria-label={t("onColStock")}
                      onChange={(e) => {
                        const raw = e.target.value.trim();
                        if (raw === "") updateProduct(p.id, { stock: null });
                        else if (/^\d{1,5}$/.test(raw)) updateProduct(p.id, { stock: Number(raw) });
                      }} />
                  </td>
                  <td className="py-1 pr-2">
                    <input type="checkbox" checked={p.badges.includes("sponsored")} aria-label={t("onColSponsored")}
                      onChange={(e) => updateProduct(p.id, { badges: e.target.checked ? [...p.badges, "sponsored"] : p.badges.filter((b) => b !== "sponsored") })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {products.length > shown.length && !filter && <p className="text-xs text-muted-foreground">{t("onProductsMore", { count: products.length - shown.length })}</p>}
      </Card>
    </fieldset>
  );
}

function Card({ title, hint, className, children }: { title: string; hint?: string; className?: string; children: ReactNode }) {
  return (
    <section className={`panel flex min-w-0 flex-col gap-3 rounded-[1.4rem] p-4 text-sm ${className ?? ""}`}>
      <div>
        <h3 className="font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[180px_minmax(0,1fr)] sm:items-center">
      <div>
        <div className="text-xs font-medium">{label}</div>
        {hint && <div className="text-[0.7rem] text-muted-foreground">{hint}</div>}
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Toggle({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2 text-xs">
      <input type="checkbox" className="mt-0.5" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        <span className="font-medium">{label}</span>
        {hint && <span className="block text-[0.7rem] text-muted-foreground">{hint}</span>}
      </span>
    </label>
  );
}

function Select({ label, value, onChange, choices }: { label: string; value: string; onChange: (v: string) => void; choices: [string, string][] }) {
  return (
    <select className="h-9 w-full rounded-md border bg-background px-2 text-sm" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      {choices.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
    </select>
  );
}

function NumberInput({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <Input type="number" className="h-9 w-24" aria-label={label} min={min} max={max} value={value}
      onChange={(e) => onChange(Math.min(max, Math.max(min, Math.round(Number(e.target.value) || 0))))} />
  );
}

/** A price typed in the currency's major unit, stored in its minor unit. */
function Money({ label, value, currency, text, onTextChange, onChange }: {
  label: string; value: number; currency: string; text: string | undefined;
  onTextChange: (text: string) => void; onChange: (v: number) => void;
}) {
  const displayed = text ?? majorUnitText(value, currency);
  const invalid = toMinor(displayed, minorUnitDivisor(currency)) === null;
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-1">
      <Input className="h-8 w-24" inputMode="decimal" value={displayed} aria-label={label} aria-invalid={invalid || undefined}
        onChange={(e) => {
          onTextChange(e.target.value);
          const minor = toMinor(e.target.value, minorUnitDivisor(currency));
          if (minor !== null) onChange(minor);
        }} />
      <span className="text-[0.7rem] text-muted-foreground">{currency}</span>
      {invalid && <span className="text-[0.7rem] text-destructive">{t("onInvalidAmount")}</span>}
    </div>
  );
}
