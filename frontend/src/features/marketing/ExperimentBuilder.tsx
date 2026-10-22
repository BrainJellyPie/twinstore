// A/B test builder: the control is a saved layout; each variant is a list of changes to it (price, discount with
// a was-price tag, promotion sign, a move to eye level, new package art, category pricing). Every variant runs on
// the same shoppers as the control, so the differences come from the change.

import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpDown, BadgePercent, Copy, Eye, FlaskConical, Loader2, Package, Plus, Sparkles, Tag, Tags, Trash2, Wand2, X } from "lucide-react";

import * as api from "@/shared/api/client";
import { designExperiment, marketingKeys, startExperiment, type ChangeKind, type ExperimentDesign, type ExperimentEngine, type ExperimentRequest, type JobStatus, type VariantChange } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney, majorUnitText, minorUnitDivisor } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { usePackages } from "./hooks";
import { storeCategories, storeFixtures, toMinor, type Fixture, type Product } from "./products";

const KINDS: { kind: ChangeKind; label: MessageKey; icon: typeof Tag; hint: MessageKey }[] = [
  { kind: "discount", label: "mkKindDiscount", icon: BadgePercent, hint: "mkKindDiscountHint" },
  { kind: "price", label: "mkKindPrice", icon: Tag, hint: "mkKindPriceHint" },
  { kind: "promo", label: "mkKindPromo", icon: Sparkles, hint: "mkKindPromoHint" },
  { kind: "move", label: "mkKindMove", icon: ArrowUpDown, hint: "mkKindMoveHint" },
  { kind: "package", label: "mkKindPackage", icon: Package, hint: "mkKindPackageHint" },
  { kind: "category_price", label: "mkKindCategoryPrice", icon: Tags, hint: "mkKindCategoryPriceHint" },
];
const PROMOS = ["1+1", "2+1", "SALE", "-30%", "NEW", "LIMITED"];
const LEVELS: (MessageKey | null)[] = [null, "mkLevelBottom", "mkLevelKnee", "mkLevelEye", "mkLevelTop"];
type Translate = ReturnType<typeof useI18n>["t"];
const levelText = (level: number, t: Translate) => { const key = LEVELS[level]; return key ? t(key) : t("mkLevelN", { level }); };

interface DraftChange extends VariantChange { id: string }
interface DraftVariant { id: string; name: string; changes: DraftChange[] }

let seq = 0;
const uid = () => `c${++seq}`;

function describeChange(c: VariantChange, products: Map<string, Product>, fixtures: Map<string, Fixture>, currency: string, t: Translate): string {
  const name = products.get(c.sku ?? "")?.name ?? c.sku ?? "";
  switch (c.kind) {
    case "price": return t("mkDescPrice", { name, price: c.price != null ? formatMoney(c.price, currency) : "…" });
    case "discount": return t("mkDescDiscount", { name, percent: c.percent != null ? String(c.percent) : "…" });
    case "promo": return t("mkDescPromo", { name, promo: c.promo || "SALE" });
    case "move": return t("mkDescMove", { name, fixture: fixtures.get(c.rack_id ?? "")?.name ?? "…", level: levelText(c.level ?? 3, t) });
    case "package": return t("mkDescPackage", { name });
    case "category_price": return t("mkDescCategory", { category: c.category || "…", percent: `${c.percent != null && c.percent >= 0 ? "+" : ""}${c.percent ?? 0}` }) + (c.charm ? t("mkDescCharm") : "");
  }
}

function ready(c: VariantChange): boolean {
  switch (c.kind) {
    case "price": return !!c.sku && c.price != null;
    case "discount": return !!c.sku && c.percent != null && c.percent < 0;
    case "promo": return !!c.sku;
    case "move": return !!c.sku && !!c.rack_id;
    case "package": return !!c.sku && !!c.asset_id;
    case "category_price": return !!c.category && c.percent != null;
  }
}

export function ExperimentBuilder({ projectId, setupId, products, store, currency, initial, prefill, onPrefillHandled, onStarted }: {
  projectId: string; setupId: string; products: Product[]; store: Parameters<typeof storeFixtures>[0]; currency: string;
  /** A finished test to start from ("duplicate and edit"). */
  initial?: ExperimentRequest | null;
  /** A question routed here from the command palette: filled in and drafted at once. */
  prefill?: { text: string; id: number };
  onPrefillHandled?: (id: number) => void;
  onStarted: (job: JobStatus) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const fixtures = useMemo(() => storeFixtures(store), [store]);
  const categories = useMemo(() => storeCategories(store), [store]);
  const productMap = useMemo(() => new Map(products.map((p) => [p.sku, p])), [products]);
  const fixtureMap = useMemo(() => new Map(fixtures.map((f) => [f.id, f])), [fixtures]);
  const packages = usePackages(projectId).data ?? [];
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });

  const [name, setName] = useState(initial?.name ? t("mkCopySuffix", { name: initial.name }).slice(0, 80) : "");
  const [hero, setHero] = useState(initial?.variants.flatMap((v) => v.changes.map((c) => c.sku ?? "")).find(Boolean) ?? "");
  const [variants, setVariants] = useState<DraftVariant[]>(() => initial?.variants.length
    ? initial.variants.map((v) => ({ id: uid(), name: v.name, changes: v.changes.map((c) => ({ ...c, id: uid() })) }))
    : [{ id: uid(), name: t("mkVariantDefault", { letter: "B" }), changes: [] }]);
  const [engine, setEngine] = useState<ExperimentEngine>(initial?.engine ?? "rule");
  const [model, setModel] = useState(initial?.model ?? "");
  const [panel, setPanel] = useState(initial?.panel ?? 300);
  const [extraFocus, setExtraFocus] = useState<string[]>(() => {
    const changed = new Set(initial?.variants.flatMap((v) => v.changes.map((c) => c.sku ?? "")) ?? []);
    return (initial?.focus_skus ?? []).filter((s) => !changed.has(s));
  });

  // A switch to vision shoppers (by hand, by a drafted design or a recipe) starts from a panel sized for model calls:
  // 300 rule shoppers per arm are seconds, 300 vision shoppers per arm are thousands of model calls.
  const switchEngine = (next: ExperimentEngine) => {
    setEngine(next);
    setPanel((current) => (next === "vlm" ? Math.min(current, 80) : Math.max(current, 300)));
  };
  const usesPackage = variants.some((v) => v.changes.some((c) => c.kind === "package"));
  const focus = [...new Set([...variants.flatMap((v) => v.changes.map((c) => c.sku ?? "")).filter(Boolean), ...extraFocus])].slice(0, 20);
  const complete = variants.length > 0 && variants.every((v) => v.name.trim() && v.changes.length > 0 && v.changes.every(ready));
  const blocked = usesPackage && engine === "rule" ? t("mkBlockedPackages") : "";

  const run = useMutation({
    mutationFn: () => startExperiment(projectId, {
      setup_id: setupId, name: name.trim(), engine, model: engine === "vlm" ? model : "", panel, focus_skus: focus,
      variants: variants.map((v) => ({ name: v.name.trim(), changes: v.changes.map(({ id: _id, ...c }) => c) })),
    }),
    onSuccess: async (job) => {
      await qc.invalidateQueries({ queryKey: marketingKeys.experiments(projectId) });
      onStarted(job);
    },
  });

  // Draft the whole test from the question it should answer; everything stays editable.
  const [question, setQuestion] = useState("");
  const questionLength = Array.from(question.trim()).length;
  const [accepted, setAccepted] = useState<{
    design: ExperimentDesign; question: string; projectId: string; setupId: string; currency: string;
    store: typeof store; products: Product[]; variants: DraftVariant[]; engine: ExperimentEngine;
    name: string; hero: string; extraFocus: string[];
  } | null>(null);
  const draft = useMutation({
    mutationFn: (q: string) => designExperiment(projectId, { question: q.trim(), setup_id: setupId }),
  });
  const { reset } = draft;
  useLayoutEffect(() => reset(), [question, projectId, setupId, currency, store, products, variants, engine, name, hero, extraFocus, reset]);
  const requestDraft = (asked: string, replacePending = false) => {
    if (Array.from(asked.trim()).length < 5 || (draft.isPending && !replacePending)) return;
    draft.mutate(asked, { onSuccess: (d) => {
      const nextVariants = d.variants.map((v) => ({ id: uid(), name: v.name, changes: v.changes.map((c) => ({ ...c, id: uid() })) }));
      const nextHero = d.variants.flatMap((v) => v.changes.map((c) => c.sku ?? "")).find(Boolean) || hero;
      const nextFocus = d.focus_skus.filter((s) => !d.variants.some((v) => v.changes.some((c) => c.sku === s)));
      const nextName = name.trim() ? name : d.name;
      setVariants(nextVariants);
      if (d.engine !== engine) switchEngine(d.engine);
      setHero(nextHero);
      setExtraFocus(nextFocus);
      setName(nextName);
      setAccepted({ design: d, question: asked, projectId, setupId, currency, store, products,
        variants: nextVariants, engine: d.engine, name: nextName, hero: nextHero, extraFocus: nextFocus });
    } });
  };
  const designed = accepted?.question === question && accepted.projectId === projectId && accepted.setupId === setupId
    && accepted.currency === currency && accepted.store === store && accepted.products === products && accepted.variants === variants
    && accepted.engine === engine && accepted.name === name && accepted.hero === hero && accepted.extraFocus === extraFocus ? accepted.design : null;

  const prefillId = prefill?.id;
  const prefillText = prefill?.text;
  const queueDraft = useQueuedStart((asked: string) => requestDraft(asked, true));
  useEffect(() => {
    if (prefillId === undefined || !prefillText) return;
    const text = Array.from(prefillText).slice(0, 500).join("");
    setQuestion(text);
    queueDraft(text);
    onPrefillHandled?.(prefillId);
  }, [prefillId, prefillText, queueDraft, onPrefillHandled]);

  const update = (vid: string, fn: (v: DraftVariant) => DraftVariant) => setVariants((vs) => vs.map((v) => (v.id === vid ? fn(v) : v)));
  const heroProduct = productMap.get(hero);
  const heroRack = fixtures.find((f) => heroProduct?.racks.includes(f.name));
  const linkedPack = packages.find((p) => p.sku === hero) ?? packages[0];

  const recipes: { label: MessageKey; hint: MessageKey; build: () => DraftVariant[]; needs?: string }[] = [
    {
      label: "mkRecipeLadder", hint: "mkRecipeLadderHint",
      build: () => [-10, -20, -30].map((pct) => ({ id: uid(), name: `${pct} %`, changes: [{ id: uid(), kind: "discount" as const, sku: hero, percent: pct }] })),
    },
    {
      label: "mkRecipeOrSign", hint: "mkRecipeOrSignHint",
      build: () => [
        { id: uid(), name: "−20 %", changes: [{ id: uid(), kind: "discount" as const, sku: hero, percent: -20 }] },
        { id: uid(), name: t("mkSaleSign"), changes: [{ id: uid(), kind: "promo" as const, sku: hero, promo: "SALE" }] },
        { id: uid(), name: "1+1", changes: [{ id: uid(), kind: "promo" as const, sku: hero, promo: "1+1" }] },
      ],
    },
    {
      label: "mkRecipeEye", hint: "mkRecipeEyeHint",
      build: () => heroRack ? [
        { id: uid(), name: t("mkLevelEye"), changes: [{ id: uid(), kind: "move" as const, sku: hero, rack_id: heroRack.id, level: 3 }] },
        { id: uid(), name: t("mkBottomShelf"), changes: [{ id: uid(), kind: "move" as const, sku: hero, rack_id: heroRack.id, level: 1 }] },
      ] : [],
    },
    {
      label: "mkRecipeSweep", hint: "mkRecipeSweepHint",
      build: () => heroProduct ? [-30, -15, 15, 30].map((pct) => ({
        id: uid(), name: t("mkSweepName", { change: `${pct > 0 ? "+" : "−"}${Math.abs(pct)}` }),
        changes: [{ id: uid(), kind: "price" as const, sku: hero, price: Math.max(1, Math.round(heroProduct.price * (1 + pct / 100))), keep_reference: true }],
      })) : [],
    },
    {
      label: "mkRecipeUp", hint: "mkRecipeUpHint",
      build: () => heroProduct ? [10, 20].map((pct) => ({
        id: uid(), name: `+${pct} %`, changes: [{ id: uid(), kind: "price" as const, sku: hero, price: Math.round(heroProduct.price * (1 + pct / 100)), keep_reference: true }],
      })) : [],
    },
    {
      label: "mkRecipePack", hint: "mkRecipePackHint", needs: "vlm",
      build: () => linkedPack ? [{ id: uid(), name: t("mkRecipePack"), changes: [{ id: uid(), kind: "package" as const, sku: hero, asset_id: linkedPack.asset_id }] }] : [],
    },
  ];

  return (
    <div className="space-y-4">
      <section className="glass space-y-3 rounded-2xl p-4">
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-foreground/[0.035] p-2">
          <Sparkles className="ml-1 size-4 shrink-0 text-primary" aria-hidden />
          <Input value={question} onChange={(e) => setQuestion(Array.from(e.target.value).slice(0, 500).join(""))}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); requestDraft(question); } }}
            placeholder={t("mkQuestionPlaceholder")}
            aria-label={t("mkQuestionForTest")} className="h-9 min-w-[14rem] flex-1 bg-card" />
          <Button type="button" size="sm" variant="outline" disabled={questionLength < 5 || draft.isPending} onClick={() => requestDraft(question)}>
            {draft.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("mkDraftTest")}
          </Button>
          {designed && (
            <div className="basis-full space-y-0.5 px-1 text-xs text-muted-foreground">
              <p>{designed.rationale} {t("mkCheckVariants")}</p>
              {designed.warnings.map((w) => <p key={w}>· {w}</p>)}
            </div>
          )}
          {draft.error && <p role="alert" className="basis-full px-1 text-xs text-destructive">{draft.error.message}</p>}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-[15rem] flex-1 flex-col gap-1">
            <span className="text-xs text-muted-foreground">{t("mkHeroProduct")}</span>
            <ProductSelect products={products} value={hero} onChange={setHero} placeholder={t("mkHeroPlaceholder")} />
          </label>
          <label className="flex min-w-[12rem] flex-1 flex-col gap-1">
            <span className="text-xs text-muted-foreground">{t("mkTestNameOptional")}</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("mkTestNamePlaceholder")} maxLength={80} />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          {recipes.map((r) => (
            <button
              key={r.label}
              type="button"
              disabled={!hero}
              onClick={() => {
                const built = r.build();
                if (built.length) {
                  setVariants(built);
                  if (r.needs === "vlm" && engine !== "vlm") switchEngine("vlm");
                  if (!name) setName(`${heroProduct?.name ?? hero} · ${t(r.label).toLowerCase()}`);
                }
              }}
              className="group flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs transition-colors enabled:hover:border-primary/60 disabled:opacity-45"
            >
              <Wand2 className="size-3.5 text-primary" />
              <span><b className="block text-[0.8rem] font-semibold">{t(r.label)}</b><span className="text-muted-foreground">{t(r.hint)}</span></span>
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-3 xl:grid-cols-2">
        <div className="rounded-2xl border border-dashed p-4">
          <div className="mb-1 flex items-center gap-2">
            <span className="grid size-6 place-items-center rounded-md bg-foreground/[0.07] text-xs font-bold">A</span>
            <span className="font-semibold">{t("mkControl")}</span>
          </div>
          <p className="text-sm text-muted-foreground">{t("mkControlDesc", { products: products.length, fixtures: fixtures.length })}</p>
          {heroProduct && (
            <div className="mt-3 rounded-xl bg-foreground/[0.035] px-3 py-2 text-sm">
              <b>{heroProduct.name}</b> · {formatMoney(heroProduct.price, currency)}
              {heroProduct.regularPrice > 0 && <span className="text-muted-foreground line-through"> {formatMoney(heroProduct.regularPrice, currency)}</span>}
              <span className="text-muted-foreground"> · {t(heroProduct.facings > 1 ? "mkFacings" : "mkFacing", { count: heroProduct.facings })} · {heroProduct.racks.join(", ")}</span>
            </div>
          )}
        </div>
        {variants.map((v, i) => (
          <VariantCard
            key={v.id}
            letter={String.fromCharCode(66 + i)}
            variant={v}
            products={products}
            fixtures={fixtures}
            categories={categories}
            packages={packages}
            projectId={projectId}
            currency={currency}
            defaultSku={hero}
            onChange={(fn) => update(v.id, fn)}
            onDuplicate={variants.length < 6 ? () => setVariants((vs) => [...vs.slice(0, i + 1), { ...v, id: uid(), name: t("mkVariantCopy", { name: v.name }).slice(0, 40), changes: v.changes.map((c) => ({ ...c, id: uid() })) }, ...vs.slice(i + 1)]) : undefined}
            onRemove={variants.length > 1 ? () => setVariants((vs) => vs.filter((x) => x.id !== v.id)) : undefined}
            describe={(c) => describeChange(c, productMap, fixtureMap, currency, t)}
          />
        ))}
        {variants.length < 6 && (
          <button type="button" onClick={() => setVariants((vs) => [...vs, { id: uid(), name: t("mkVariantDefault", { letter: String.fromCharCode(66 + vs.length) }), changes: [] }])}
            className="flex min-h-[7rem] items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-foreground/12 text-sm text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground">
            <Plus className="size-4" /> {t("mkAddVariant")}
          </button>
        )}
      </div>

      <section className="glass grid gap-4 rounded-2xl p-4 lg:grid-cols-[1.2fr_1fr_1fr]">
        <div className="space-y-2">
          <span className="text-xs text-muted-foreground">{t("mkShoppers")}</span>
          <div className="grid grid-cols-2 gap-1.5">
            {([["rule", "mkRuleShoppers", "mkRuleShoppersHint"], ["vlm", "mkVisionShoppers", "mkVisionShoppersHint"]] as const).map(([k, title, hint]) => (
              <button key={k} type="button" onClick={() => switchEngine(k)}
                className={cn("rounded-xl border px-3 py-2 text-left transition-colors", engine === k ? "border-primary bg-primary/[0.07]" : "hover:border-foreground/20")}>
                <b className="block text-sm">{t(title)}</b>
                <span className="text-[0.7rem] text-muted-foreground">{t(hint)}</span>
              </button>
            ))}
          </div>
          {engine === "vlm" && (
            <select className="h-9 w-full rounded-xl border bg-card/60 px-2.5 text-sm" value={model} onChange={(e) => setModel(e.target.value)} aria-label={t("studioVisionModel")}>
              <option value="">{t("studioAppVisionModel")}</option>
              {models.filter((m) => m.vision).map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
            </select>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-baseline justify-between text-xs text-muted-foreground">
            <span>{t("mkPanelSame")}</span>
            <span className="num text-sm font-semibold text-foreground">{panel}</span>
          </div>
          <input type="range" min={20} max={engine === "vlm" ? 600 : 3000} step={10} value={panel} onChange={(e) => setPanel(Number(e.target.value))} className="w-full" aria-label={t("mkPanelSize")} />
          <p className="text-[0.7rem] text-muted-foreground">
            {t(engine === "vlm" ? "mkSimulatedTripsModel" : "mkSimulatedTrips", { count: (variants.length + 1) * panel })}
            {panel < 100 && t("mkSmallPanel")}
          </p>
        </div>
        <div className="space-y-2">
          <span className="text-xs text-muted-foreground">{t("mkTrack")}</span>
          <div className="flex flex-wrap gap-1.5">
            {focus.length === 0 && <span className="text-xs text-muted-foreground">{t("mkTrackAuto")}</span>}
            {focus.map((sku) => (
              <span key={sku} className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
                {productMap.get(sku)?.name ?? sku}
                {extraFocus.includes(sku) && (
                  <button type="button" onClick={() => setExtraFocus((f) => f.filter((x) => x !== sku))} aria-label={t("mkStopTracking", { sku })}><X className="size-3" /></button>
                )}
              </span>
            ))}
          </div>
          <ProductSelect products={products} value="" onChange={(s) => s && setExtraFocus((f) => [...new Set([...f, s])])} placeholder={t("mkTrackAnother")} small />
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        {(blocked || run.error) && <p className="mr-auto text-sm text-destructive">{blocked || run.error?.message}</p>}
        {!complete && !blocked && <p className="mr-auto text-sm text-muted-foreground">{t("mkIncomplete")}</p>}
        <Button size="lg" disabled={!complete || !!blocked || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <FlaskConical className="size-4" />}
          {t("mkRunAb")}
        </Button>
      </div>
    </div>
  );
}

function ProductSelect({ products, value, onChange, placeholder, small = false }: {
  products: Product[]; value: string; onChange: (sku: string) => void; placeholder: string; small?: boolean;
}) {
  const { t, locale } = useI18n();
  const other = t("mkOtherGroup");
  const groups = useMemo(() => {
    const g = new Map<string, Product[]>();
    for (const p of products) {
      const k = p.racks[0] ?? other;
      g.set(k, [...(g.get(k) ?? []), p]);
    }
    return [...g.entries()].sort(([a], [b]) => a.localeCompare(b, locale));
  }, [products, other, locale]);
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={cn("w-full min-w-0 rounded-xl border bg-card/60 px-2.5", small ? "h-8 text-xs" : "h-10 text-sm")}>
      <option value="">{placeholder}</option>
      {groups.map(([rack, ps]) => (
        <optgroup key={rack} label={rack}>
          {ps.map((p) => <option key={p.sku} value={p.sku}>{p.name}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

function VariantCard({ letter, variant, products, fixtures, categories, packages, projectId, currency, defaultSku, onChange, onDuplicate, onRemove, describe }: {
  letter: string; variant: DraftVariant; products: Product[]; fixtures: Fixture[]; categories: string[]; packages: api.PackageAsset[];
  projectId: string; currency: string; defaultSku: string;
  onChange: (fn: (v: DraftVariant) => DraftVariant) => void; onDuplicate?: () => void; onRemove?: () => void; describe: (c: VariantChange) => string;
}) {
  const { t } = useI18n();
  const setChange = (id: string, patch: Partial<VariantChange>) =>
    onChange((v) => ({ ...v, changes: v.changes.map((c) => (c.id === id ? { ...c, ...patch } : c)) }));
  const add = (kind: ChangeKind) => onChange((v) => ({
    ...v,
    changes: [...v.changes, {
      id: uid(), kind, sku: kind === "category_price" ? "" : defaultSku,
      ...(kind === "discount" ? { percent: -20 } : kind === "promo" ? { promo: "SALE" } : kind === "move" ? { level: 3 } : kind === "category_price" ? { percent: -10 } : {}),
    }],
  }));
  return (
    <div className="rounded-2xl border bg-card/70 p-4 shadow-[0_18px_40px_-30px_rgb(0_0_0/0.4)]">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid size-6 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">{letter}</span>
        <Input value={variant.name} onChange={(e) => onChange((v) => ({ ...v, name: e.target.value }))} maxLength={40} className="h-8 flex-1 font-semibold" aria-label={t("mkVariantName")} />
        {onDuplicate && <button type="button" onClick={onDuplicate} className="rounded-lg p-1.5 text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground" aria-label={t("mkDuplicateVariant")}><Copy className="size-4" /></button>}
        {onRemove && <button type="button" onClick={onRemove} className="rounded-lg p-1.5 text-muted-foreground hover:bg-foreground/[0.06] hover:text-destructive" aria-label={t("mkRemoveVariant")}><Trash2 className="size-4" /></button>}
      </div>
      <div className="space-y-2">
        {variant.changes.map((c) => (
          <ChangeEditor key={c.id} change={c} products={products} fixtures={fixtures} categories={categories} packages={packages} projectId={projectId}
            currency={currency} summary={describe(c)} onPatch={(p) => setChange(c.id, p)}
            onRemove={() => onChange((v) => ({ ...v, changes: v.changes.filter((x) => x.id !== c.id) }))} />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {KINDS.map(({ kind, label, icon: Icon, hint }) => (
          <button key={kind} type="button" title={t(hint)} onClick={() => add(kind)}
            className="inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground">
            <Icon className="size-3.5" /> {t(label)}
          </button>
        ))}
      </div>
    </div>
  );
}

function ChangeEditor({ change: c, products, fixtures, categories, packages, projectId, currency, summary, onPatch, onRemove }: {
  change: DraftChange; products: Product[]; fixtures: Fixture[]; categories: string[]; packages: api.PackageAsset[]; projectId: string;
  currency: string; summary: string; onPatch: (p: Partial<VariantChange>) => void; onRemove: () => void;
}) {
  const { t } = useI18n();
  const divisor = minorUnitDivisor(currency);
  const [priceText, setPriceText] = useState(c.price != null ? majorUnitText(c.price, currency, { fixed: true }) : "");
  const meta = KINDS.find((k) => k.kind === c.kind)!;
  const Icon = meta.icon;
  const product = products.find((p) => p.sku === c.sku);
  return (
    <div className={cn("rounded-xl border p-2.5", ready(c) ? "bg-foreground/[0.02]" : "border-warn/50 bg-warn/[0.04]")}>
      <div className="mb-2 flex items-center gap-2 text-xs">
        <Icon className="size-3.5 text-primary" />
        <span className="font-semibold">{t(meta.label)}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">{summary}</span>
        <button type="button" onClick={onRemove} className="rounded p-0.5 text-muted-foreground hover:text-destructive" aria-label={t("mkRemoveChange")}><X className="size-3.5" /></button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {c.kind !== "category_price" && (
          <div className="min-w-[11rem] flex-1"><ProductSelect products={products} value={c.sku ?? ""} onChange={(sku) => onPatch({ sku })} placeholder={t("mkProductEllipsis")} small /></div>
        )}
        {c.kind === "price" && (
          <Input value={priceText} inputMode="decimal" placeholder={product ? t("mkNowPrice", { price: formatMoney(product.price, currency) }) : t("mkPrice")} className="num h-8 w-28 text-xs"
            onChange={(e) => { setPriceText(e.target.value); onPatch({ price: toMinor(e.target.value, divisor) }); }} aria-label={t("mkNewPrice")}
            aria-invalid={priceText.trim().length > 0 && c.price == null} />
        )}
        {c.kind === "price" && (
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground" title={t("mkKeepReferenceTitle")}>
            <input type="checkbox" checked={!!c.keep_reference} onChange={(e) => onPatch({ keep_reference: e.target.checked })} /> {t("mkKeepReference")}
          </label>
        )}
        {(c.kind === "discount" || c.kind === "category_price") && (
          <div className="flex items-center gap-1">
            {(c.kind === "discount" ? [-10, -20, -30, -50] : [-10, 0, 5, 10]).map((p) => (
              <button key={p} type="button" onClick={() => onPatch({ percent: p })}
                className={cn("num rounded-md border px-1.5 py-0.5 text-xs", c.percent === p ? "border-primary bg-primary text-primary-foreground" : "hover:border-foreground/25")}>
                {p > 0 ? "+" : ""}{p}%
              </button>
            ))}
            <Input type="number" value={c.percent ?? ""} onChange={(e) => onPatch({ percent: e.target.value === "" ? null : Number(e.target.value) })}
              className="num h-7 w-16 text-xs" aria-label={t("mkPercent")} />
          </div>
        )}
        {c.kind === "discount" && product && c.percent != null && c.percent < 0 && (
          <span className="num text-xs text-muted-foreground">
            {formatMoney(product.regularPrice || product.price, currency)} → <b className="text-foreground">{formatMoney(Math.round((product.regularPrice || product.price) * (1 + c.percent / 100)), currency)}</b>
          </span>
        )}
        {c.kind === "promo" && (
          <div className="flex flex-wrap items-center gap-1">
            {PROMOS.map((p) => (
              <button key={p} type="button" onClick={() => onPatch({ promo: p })}
                className={cn("rounded-full border px-2 py-0.5 text-[0.7rem] font-semibold", c.promo === p ? "border-transparent bg-[#e8182e] text-white" : "hover:border-foreground/25")}>
                {p}
              </button>
            ))}
            <Input value={c.promo ?? ""} onChange={(e) => onPatch({ promo: e.target.value.slice(0, 24) })} className="h-7 w-20 text-xs" aria-label={t("mkSignText")} />
          </div>
        )}
        {c.kind === "move" && (
          <>
            <select value={c.rack_id ?? ""} onChange={(e) => onPatch({ rack_id: e.target.value })} className="h-8 min-w-[8rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label={t("mkFixture")}>
              <option value="">{t("mkFixtureEllipsis")}</option>
              {fixtures.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4].map((l) => (
                <button key={l} type="button" onClick={() => onPatch({ level: l })} title={levelText(l, t)}
                  className={cn("rounded-md border px-1.5 py-0.5 text-xs", c.level === l ? "border-primary bg-primary text-primary-foreground" : "hover:border-foreground/25")}>
                  {l === 3 ? <span className="inline-flex items-center gap-1"><Eye className="size-3" />3</span> : l}
                </button>
              ))}
            </div>
          </>
        )}
        {c.kind === "package" && (
          <div className="flex flex-wrap gap-1.5">
            {packages.length === 0 && <span className="text-xs text-muted-foreground">{t("mkAddImagesFirst")}</span>}
            {packages.map((p) => (
              <button key={p.asset_id} type="button" title={p.name} onClick={() => onPatch({ asset_id: p.asset_id })}
                className={cn("flex size-11 items-center justify-center overflow-hidden rounded-lg border bg-white p-0.5", c.asset_id === p.asset_id ? "border-primary ring-2 ring-primary/40" : "hover:border-foreground/25")}>
                <img src={api.packageUrl(projectId, p.asset_id)} alt={p.name} className="max-h-full max-w-full object-contain" />
              </button>
            ))}
          </div>
        )}
        {c.kind === "category_price" && (
          <>
            <select value={c.category ?? ""} onChange={(e) => onPatch({ category: e.target.value })} className="h-8 min-w-[8rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label={t("mkCategory")}>
              <option value="">{t("mkCategoryEllipsis")}</option>
              {categories.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={!!c.charm} onChange={(e) => onPatch({ charm: e.target.checked })} /> {t("mkCharm")}</label>
          </>
        )}
      </div>
    </div>
  );
}
