// The store's ad campaigns: which product each promotes, where it shows, its headline and what it costs. Saved with
// the store; compare a store with and without an ad on the same shoppers to see what the ad adds.

import { Megaphone, Plus, Trash2 } from "lucide-react";

import { AD_PLACEMENTS, type AdCampaign, type AdPlacement, type OnlineProduct } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import { majorUnitText, minorUnitDivisor, toMinor } from "@/shared/utils/money";

import { AD_PLACEMENT_HINTS, AD_PLACEMENT_LABELS } from "./labels";

const MAX_ADS = 12;

function newAdId(): string {
  return `ad_${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
}

export function AdsEditor({ ads, products, currency, onChange, costText, onCostText, onCompareWithout }: {
  ads: AdCampaign[];
  products: OnlineProduct[];
  currency: string;
  onChange: (ads: AdCampaign[]) => void;
  costText: (id: string) => string | undefined; // what is typed in a cost box, until it is a valid amount
  onCostText: (id: string, text: string) => void;
  onCompareWithout?: () => void;
}) {
  const { t } = useI18n();
  const update = (id: string, change: Partial<AdCampaign>) => onChange(ads.map((ad) => (ad.id === id ? { ...ad, ...change } : ad)));
  const popular = [...products].filter((p) => p.stock !== 0).sort((a, b) => b.weekly_sales - a.weekly_sales);
  const add = () => {
    const product = popular.find((p) => !ads.some((ad) => ad.product_id === p.id)) ?? popular[0];
    if (!product) return;
    onChange([...ads, {
      id: newAdId(), name: product.name.slice(0, 60), product_id: product.id, placement: "hero_banner", headline: "",
      pricing: "cpc", cost: minorUnitDivisor(currency) === 1 ? 500 : 50, active: true,
    }]);
  };
  return (
    <div className="space-y-3">
      {ads.length === 0 && <p className="text-xs text-muted-foreground">{t("onAdsNone")}</p>}
      <ul className="space-y-2">
        {ads.map((ad) => (
          <li key={ad.id} className="space-y-2 rounded-xl border p-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <Megaphone className="size-4 text-primary" aria-hidden />
              <Input className="h-8 min-w-40 flex-1" value={ad.name} maxLength={60} aria-label={t("onAdName")}
                onChange={(e) => update(ad.id, { name: e.target.value })} />
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={ad.active} onChange={(e) => update(ad.id, { active: e.target.checked })} /> {t("onAdActive")}
              </label>
              <Button variant="ghost" size="icon-sm" aria-label={t("onAdRemove")} onClick={() => onChange(ads.filter((x) => x.id !== ad.id))}>
                <Trash2 aria-hidden />
              </Button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="flex flex-col gap-1">
                <span className="text-muted-foreground">{t("onAdProduct")}</span>
                <select className="h-8 rounded-md border bg-background px-2" value={ad.product_id} onChange={(e) => update(ad.id, { product_id: e.target.value })}>
                  {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1" title={t(AD_PLACEMENT_HINTS[ad.placement])}>
                <span className="text-muted-foreground">{t("onAdPlacement")}</span>
                <select className="h-8 rounded-md border bg-background px-2" value={ad.placement} onChange={(e) => update(ad.id, { placement: e.target.value as AdPlacement })}>
                  {AD_PLACEMENTS.map((p) => <option key={p} value={p}>{t(AD_PLACEMENT_LABELS[p])}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="text-muted-foreground">{t("onAdHeadline")}</span>
                <Input className="h-8" value={ad.headline} maxLength={70} placeholder={t("onAdHeadlinePlaceholder")} onChange={(e) => update(ad.id, { headline: e.target.value })} />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-muted-foreground">{t("onAdPricing")}</span>
                <select className="h-8 rounded-md border bg-background px-2" value={ad.pricing} onChange={(e) => update(ad.id, { pricing: e.target.value as AdCampaign["pricing"] })}>
                  <option value="cpc">{t("onAdCpc")}</option>
                  <option value="cpm">{t("onAdCpm")}</option>
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-muted-foreground">{ad.pricing === "cpc" ? t("onAdCostClick") : t("onAdCostThousand")}</span>
                <CostInput value={ad.cost} currency={currency} label={ad.pricing === "cpc" ? t("onAdCostClick") : t("onAdCostThousand")}
                  text={costText(ad.id)} onTextChange={(text) => onCostText(ad.id, text)} onChange={(cost) => update(ad.id, { cost })} />
              </label>
            </div>
            <p className="text-[0.7rem] text-muted-foreground">{t(AD_PLACEMENT_HINTS[ad.placement])}</p>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={add} disabled={ads.length >= MAX_ADS || popular.length === 0}>
          <Plus aria-hidden /> {t("onAdAdd")}
        </Button>
        {onCompareWithout && ads.some((ad) => ad.active) && (
          <Button variant="outline" size="sm" onClick={onCompareWithout} title={t("onAdCompareHint")}>{t("onAdCompare")}</Button>
        )}
      </div>
    </div>
  );
}

function CostInput({ value, currency, label, text, onTextChange, onChange }: {
  value: number; currency: string; label: string; text: string | undefined; onTextChange: (text: string) => void;
  onChange: (v: number) => void;
}) {
  const { t } = useI18n();
  const displayed = text ?? majorUnitText(value, currency);
  const invalid = toMinor(displayed, minorUnitDivisor(currency)) === null;
  return (
    <span className="flex flex-wrap items-center gap-1">
      <Input className="h-8 w-24" inputMode="decimal" value={displayed} aria-label={label} aria-invalid={invalid || undefined}
        onChange={(e) => {
          onTextChange(e.target.value);
          const minor = toMinor(e.target.value, minorUnitDivisor(currency));
          if (minor !== null) onChange(minor);
        }} />
      <span className="text-[0.7rem] text-muted-foreground">{currency}</span>
      {invalid && <span className="text-[0.7rem] text-destructive">{t("onInvalidAmount")}</span>}
      <span className="sr-only">{t("onAdCostHint")}</span>
    </span>
  );
}
