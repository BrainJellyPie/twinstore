// A/B test builder: the control is a saved layout; each variant is a list of changes to it (price, discount with
// a was-price tag, promotion sign, a move to eye level, new package art, category pricing). Every variant runs on
// the same shoppers as the control, so the differences come from the change.

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpDown, BadgePercent, Copy, Eye, FlaskConical, Loader2, Package, Plus, Sparkles, Tag, Tags, Trash2, Wand2, X } from "lucide-react";

import * as api from "@/shared/api/client";
import { marketingKeys, startExperiment, type ChangeKind, type ExperimentEngine, type JobStatus, type VariantChange } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney, minorUnitDivisor } from "@/shared/utils/money";

import { usePackages } from "./hooks";
import { storeCategories, storeFixtures, toMinor, type Fixture, type Product } from "./products";

const KINDS: { kind: ChangeKind; label: string; icon: typeof Tag; hint: string }[] = [
  { kind: "discount", label: "Discount", icon: BadgePercent, hint: "Cut the price; the tag shows the was-price" },
  { kind: "price", label: "New price", icon: Tag, hint: "A new everyday price" },
  { kind: "promo", label: "Promo sign", icon: Sparkles, hint: "Hang 1+1, SALE, −30 % …" },
  { kind: "move", label: "Placement", icon: ArrowUpDown, hint: "Move to another fixture or shelf level" },
  { kind: "package", label: "Package", icon: Package, hint: "Show a new pack (vision shoppers)" },
  { kind: "category_price", label: "Category price", icon: Tags, hint: "Re-price a whole category" },
];
const PROMOS = ["1+1", "2+1", "SALE", "-30%", "NEW", "LIMITED"];
const LEVELS = ["", "Bottom", "Knee", "Eye level", "Top"];

interface DraftChange extends VariantChange { id: string }
interface DraftVariant { id: string; name: string; changes: DraftChange[] }

let seq = 0;
const uid = () => `c${++seq}`;

function describeChange(c: VariantChange, products: Map<string, Product>, fixtures: Map<string, Fixture>, currency: string): string {
  const name = products.get(c.sku ?? "")?.name ?? c.sku ?? "";
  switch (c.kind) {
    case "price": return `${name} at ${c.price != null ? formatMoney(c.price, currency) : "…"}`;
    case "discount": return `${name} ${c.percent ?? "…"} %`;
    case "promo": return `${name} with a “${c.promo || "SALE"}” sign`;
    case "move": return `${name} → ${fixtures.get(c.rack_id ?? "")?.name ?? "…"} · ${LEVELS[c.level ?? 3] ?? `level ${c.level}`}`;
    case "package": return `${name} in a new pack`;
    case "category_price": return `${c.category || "…"} ${c.percent != null && c.percent >= 0 ? "+" : ""}${c.percent ?? 0} %${c.charm ? ", .99 endings" : ""}`;
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

export function ExperimentBuilder({ projectId, setupId, products, store, currency, onStarted }: {
  projectId: string; setupId: string; products: Product[]; store: Parameters<typeof storeFixtures>[0]; currency: string;
  onStarted: (job: JobStatus) => void;
}) {
  const qc = useQueryClient();
  const fixtures = useMemo(() => storeFixtures(store), [store]);
  const categories = useMemo(() => storeCategories(store), [store]);
  const productMap = useMemo(() => new Map(products.map((p) => [p.sku, p])), [products]);
  const fixtureMap = useMemo(() => new Map(fixtures.map((f) => [f.id, f])), [fixtures]);
  const packages = usePackages(projectId).data ?? [];
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });

  const [name, setName] = useState("");
  const [hero, setHero] = useState("");
  const [variants, setVariants] = useState<DraftVariant[]>([{ id: uid(), name: "Variant B", changes: [] }]);
  const [engine, setEngine] = useState<ExperimentEngine>("rule");
  const [model, setModel] = useState("");
  const [panel, setPanel] = useState(300);
  const [extraFocus, setExtraFocus] = useState<string[]>([]);

  const usesPackage = variants.some((v) => v.changes.some((c) => c.kind === "package"));
  const focus = [...new Set([...variants.flatMap((v) => v.changes.map((c) => c.sku ?? "")).filter(Boolean), ...extraFocus])].slice(0, 20);
  const complete = variants.length > 0 && variants.every((v) => v.name.trim() && v.changes.length > 0 && v.changes.every(ready));
  const blocked = usesPackage && engine === "rule" ? "Packages are only visible to vision shoppers — switch the engine." : "";

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

  const update = (vid: string, fn: (v: DraftVariant) => DraftVariant) => setVariants((vs) => vs.map((v) => (v.id === vid ? fn(v) : v)));
  const heroProduct = productMap.get(hero);
  const heroRack = fixtures.find((f) => heroProduct?.racks.includes(f.name));
  const linkedPack = packages.find((p) => p.sku === hero) ?? packages[0];

  const recipes: { label: string; hint: string; build: () => DraftVariant[]; needs?: string }[] = [
    {
      label: "Discount ladder", hint: "−10 / −20 / −30 %",
      build: () => [-10, -20, -30].map((pct) => ({ id: uid(), name: `${pct} %`, changes: [{ id: uid(), kind: "discount" as const, sku: hero, percent: pct }] })),
    },
    {
      label: "Discount or sign?", hint: "−20 % vs SALE vs 1+1",
      build: () => [
        { id: uid(), name: "−20 %", changes: [{ id: uid(), kind: "discount" as const, sku: hero, percent: -20 }] },
        { id: uid(), name: "SALE sign", changes: [{ id: uid(), kind: "promo" as const, sku: hero, promo: "SALE" }] },
        { id: uid(), name: "1+1", changes: [{ id: uid(), kind: "promo" as const, sku: hero, promo: "1+1" }] },
      ],
    },
    {
      label: "Eye level", hint: "eye level vs bottom shelf",
      build: () => heroRack ? [
        { id: uid(), name: "Eye level", changes: [{ id: uid(), kind: "move" as const, sku: hero, rack_id: heroRack.id, level: 3 }] },
        { id: uid(), name: "Bottom shelf", changes: [{ id: uid(), kind: "move" as const, sku: hero, rack_id: heroRack.id, level: 1 }] },
      ] : [],
    },
    {
      label: "Price sweep", hint: "−30 % to +30 %, demand curve",
      build: () => heroProduct ? [-30, -15, 15, 30].map((pct) => ({
        id: uid(), name: `${pct > 0 ? "+" : "−"}${Math.abs(pct)} % price`,
        changes: [{ id: uid(), kind: "price" as const, sku: hero, price: Math.max(1, Math.round(heroProduct.price * (1 + pct / 100))), keep_reference: true }],
      })) : [],
    },
    {
      label: "Price up", hint: "+10 % and +20 %",
      build: () => heroProduct ? [10, 20].map((pct) => ({
        id: uid(), name: `+${pct} %`, changes: [{ id: uid(), kind: "price" as const, sku: hero, price: Math.round(heroProduct.price * (1 + pct / 100)), keep_reference: true }],
      })) : [],
    },
    {
      label: "New pack", hint: "library image on the shelf", needs: "vlm",
      build: () => linkedPack ? [{ id: uid(), name: "New pack", changes: [{ id: uid(), kind: "package" as const, sku: hero, asset_id: linkedPack.asset_id }] }] : [],
    },
  ];

  return (
    <div className="space-y-4">
      <section className="glass space-y-3 rounded-2xl p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-[15rem] flex-1 flex-col gap-1">
            <span className="text-xs text-muted-foreground">Product the test is about</span>
            <ProductSelect products={products} value={hero} onChange={setHero} placeholder="Choose a product for a quick start…" />
          </label>
          <label className="flex min-w-[12rem] flex-1 flex-col gap-1">
            <span className="text-xs text-muted-foreground">Test name (optional)</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Summer price test" maxLength={80} />
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
                  if (r.needs === "vlm") setEngine("vlm");
                  if (!name) setName(`${heroProduct?.name ?? hero} · ${r.label.toLowerCase()}`);
                }
              }}
              className="group flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs transition-colors enabled:hover:border-primary/60 disabled:opacity-45"
            >
              <Wand2 className="size-3.5 text-primary" />
              <span><b className="block text-[0.8rem] font-semibold">{r.label}</b><span className="text-muted-foreground">{r.hint}</span></span>
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-3 xl:grid-cols-2">
        <div className="rounded-2xl border border-dashed p-4">
          <div className="mb-1 flex items-center gap-2">
            <span className="grid size-6 place-items-center rounded-md bg-foreground/[0.07] text-xs font-bold">A</span>
            <span className="font-semibold">Control</span>
          </div>
          <p className="text-sm text-muted-foreground">The layout as saved: {products.length} products on {fixtures.length} fixtures. Every variant starts from it.</p>
          {heroProduct && (
            <div className="mt-3 rounded-xl bg-foreground/[0.035] px-3 py-2 text-sm">
              <b>{heroProduct.name}</b> · {formatMoney(heroProduct.price, currency)}
              {heroProduct.regularPrice > 0 && <span className="text-muted-foreground line-through"> {formatMoney(heroProduct.regularPrice, currency)}</span>}
              <span className="text-muted-foreground"> · {heroProduct.facings} facing{heroProduct.facings > 1 ? "s" : ""} · {heroProduct.racks.join(", ")}</span>
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
            onDuplicate={variants.length < 6 ? () => setVariants((vs) => [...vs.slice(0, i + 1), { ...v, id: uid(), name: `${v.name} copy`.slice(0, 40), changes: v.changes.map((c) => ({ ...c, id: uid() })) }, ...vs.slice(i + 1)]) : undefined}
            onRemove={variants.length > 1 ? () => setVariants((vs) => vs.filter((x) => x.id !== v.id)) : undefined}
            describe={(c) => describeChange(c, productMap, fixtureMap, currency)}
          />
        ))}
        {variants.length < 6 && (
          <button type="button" onClick={() => setVariants((vs) => [...vs, { id: uid(), name: `Variant ${String.fromCharCode(66 + vs.length)}`, changes: [] }])}
            className="flex min-h-[7rem] items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-foreground/12 text-sm text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground">
            <Plus className="size-4" /> Add a variant
          </button>
        )}
      </div>

      <section className="glass grid gap-4 rounded-2xl p-4 lg:grid-cols-[1.2fr_1fr_1fr]">
        <div className="space-y-2">
          <span className="text-xs text-muted-foreground">Shoppers</span>
          <div className="grid grid-cols-2 gap-1.5">
            {([["rule", "Rule shoppers", "seconds, free · price & placement"], ["vlm", "Vision shoppers", "a model looks at each shelf · sees packs & signs"]] as const).map(([k, t, d]) => (
              <button key={k} type="button" onClick={() => { setEngine(k); setPanel(k === "vlm" ? Math.min(panel, 80) : Math.max(panel, 300)); }}
                className={cn("rounded-xl border px-3 py-2 text-left transition-colors", engine === k ? "border-primary bg-primary/[0.07]" : "hover:border-foreground/20")}>
                <b className="block text-sm">{t}</b>
                <span className="text-[0.7rem] text-muted-foreground">{d}</span>
              </button>
            ))}
          </div>
          {engine === "vlm" && (
            <select className="h-9 w-full rounded-xl border bg-card/60 px-2.5 text-sm" value={model} onChange={(e) => setModel(e.target.value)} aria-label="Vision model">
              <option value="">App's vision model</option>
              {models.filter((m) => m.vision).map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
            </select>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-baseline justify-between text-xs text-muted-foreground">
            <span>Panel (same people in every arm)</span>
            <span className="num text-sm font-semibold text-foreground">{panel}</span>
          </div>
          <input type="range" min={20} max={engine === "vlm" ? 600 : 3000} step={10} value={panel} onChange={(e) => setPanel(Number(e.target.value))} className="w-full" aria-label="Panel size" />
          <p className="text-[0.7rem] text-muted-foreground">
            {(variants.length + 1) * panel} simulated trips{engine === "vlm" ? " through the model — each trip makes several model calls" : ""}.
            {panel < 100 && " Under 100 shoppers, differences below ~5 % are noise."}
          </p>
        </div>
        <div className="space-y-2">
          <span className="text-xs text-muted-foreground">Products to track</span>
          <div className="flex flex-wrap gap-1.5">
            {focus.length === 0 && <span className="text-xs text-muted-foreground">Products changed in the variants are tracked automatically.</span>}
            {focus.map((sku) => (
              <span key={sku} className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
                {productMap.get(sku)?.name ?? sku}
                {extraFocus.includes(sku) && (
                  <button type="button" onClick={() => setExtraFocus((f) => f.filter((x) => x !== sku))} aria-label={`Stop tracking ${sku}`}><X className="size-3" /></button>
                )}
              </span>
            ))}
          </div>
          <ProductSelect products={products} value="" onChange={(s) => s && setExtraFocus((f) => [...new Set([...f, s])])} placeholder="+ track another product (e.g. a rival)" small />
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        {(blocked || run.error) && <p className="mr-auto text-sm text-destructive">{blocked || run.error?.message}</p>}
        {!complete && !blocked && <p className="mr-auto text-sm text-muted-foreground">Give every variant at least one complete change.</p>}
        <Button size="lg" disabled={!complete || !!blocked || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <FlaskConical className="size-4" />}
          Run A/B test
        </Button>
      </div>
    </div>
  );
}

function ProductSelect({ products, value, onChange, placeholder, small = false }: {
  products: Product[]; value: string; onChange: (sku: string) => void; placeholder: string; small?: boolean;
}) {
  const groups = useMemo(() => {
    const g = new Map<string, Product[]>();
    for (const p of products) {
      const k = p.racks[0] ?? "Other";
      g.set(k, [...(g.get(k) ?? []), p]);
    }
    return [...g.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [products]);
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
  const setChange = (id: string, patch: Partial<VariantChange>) =>
    onChange((v) => ({ ...v, changes: v.changes.map((c) => (c.id === id ? { ...c, ...patch } : c)) }));
  const add = (kind: ChangeKind) => onChange((v) => ({
    ...v,
    changes: [...v.changes, {
      id: uid(), kind, sku: kind === "category_price" ? "" : defaultSku,
      ...(kind === "discount" ? { percent: -20 } : kind === "promo" ? { promo: "SALE" } : kind === "move" ? { level: 3 } : kind === "category_price" ? { percent: 0, charm: true } : {}),
    }],
  }));
  return (
    <div className="rounded-2xl border bg-card/70 p-4 shadow-[0_18px_40px_-30px_rgb(0_0_0/0.4)]">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid size-6 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">{letter}</span>
        <Input value={variant.name} onChange={(e) => onChange((v) => ({ ...v, name: e.target.value }))} maxLength={40} className="h-8 flex-1 font-semibold" aria-label="Variant name" />
        {onDuplicate && <button type="button" onClick={onDuplicate} className="rounded-lg p-1.5 text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground" aria-label="Duplicate variant"><Copy className="size-4" /></button>}
        {onRemove && <button type="button" onClick={onRemove} className="rounded-lg p-1.5 text-muted-foreground hover:bg-foreground/[0.06] hover:text-destructive" aria-label="Remove variant"><Trash2 className="size-4" /></button>}
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
          <button key={kind} type="button" title={hint} onClick={() => add(kind)}
            className="inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground">
            <Icon className="size-3.5" /> {label}
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
  const divisor = minorUnitDivisor(currency);
  const [priceText, setPriceText] = useState(c.price != null ? String(c.price / divisor) : "");
  const meta = KINDS.find((k) => k.kind === c.kind)!;
  const Icon = meta.icon;
  const product = products.find((p) => p.sku === c.sku);
  return (
    <div className={cn("rounded-xl border p-2.5", ready(c) ? "bg-foreground/[0.02]" : "border-warn/50 bg-warn/[0.04]")}>
      <div className="mb-2 flex items-center gap-2 text-xs">
        <Icon className="size-3.5 text-primary" />
        <span className="font-semibold">{meta.label}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">{summary}</span>
        <button type="button" onClick={onRemove} className="rounded p-0.5 text-muted-foreground hover:text-destructive" aria-label="Remove change"><X className="size-3.5" /></button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {c.kind !== "category_price" && (
          <div className="min-w-[11rem] flex-1"><ProductSelect products={products} value={c.sku ?? ""} onChange={(sku) => onPatch({ sku })} placeholder="Product…" small /></div>
        )}
        {c.kind === "price" && (
          <Input value={priceText} inputMode="decimal" placeholder={product ? `now ${formatMoney(product.price, currency)}` : "Price"} className="num h-8 w-28 text-xs"
            onChange={(e) => { setPriceText(e.target.value); onPatch({ price: toMinor(e.target.value, divisor) }); }} aria-label="New price"
            aria-invalid={priceText.trim().length > 0 && c.price == null} />
        )}
        {c.kind === "price" && (
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground" title="Shoppers compare the new price with the current one, as just after a change (reference price). Rule shoppers only react to price this way.">
            <input type="checkbox" checked={!!c.keep_reference} onChange={(e) => onPatch({ keep_reference: e.target.checked })} /> shoppers remember the current price
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
              className="num h-7 w-16 text-xs" aria-label="Percent" />
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
            <Input value={c.promo ?? ""} onChange={(e) => onPatch({ promo: e.target.value.slice(0, 24) })} className="h-7 w-20 text-xs" aria-label="Sign text" />
          </div>
        )}
        {c.kind === "move" && (
          <>
            <select value={c.rack_id ?? ""} onChange={(e) => onPatch({ rack_id: e.target.value })} className="h-8 min-w-[8rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label="Fixture">
              <option value="">Fixture…</option>
              {fixtures.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4].map((l) => (
                <button key={l} type="button" onClick={() => onPatch({ level: l })} title={LEVELS[l]}
                  className={cn("rounded-md border px-1.5 py-0.5 text-xs", c.level === l ? "border-primary bg-primary text-primary-foreground" : "hover:border-foreground/25")}>
                  {l === 3 ? <span className="inline-flex items-center gap-1"><Eye className="size-3" />3</span> : l}
                </button>
              ))}
            </div>
          </>
        )}
        {c.kind === "package" && (
          <div className="flex flex-wrap gap-1.5">
            {packages.length === 0 && <span className="text-xs text-muted-foreground">Add images in the Products tab first.</span>}
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
            <select value={c.category ?? ""} onChange={(e) => onPatch({ category: e.target.value })} className="h-8 min-w-[8rem] rounded-lg border bg-card/60 px-1.5 text-xs" aria-label="Category">
              <option value="">Category…</option>
              {categories.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={!!c.charm} onChange={(e) => onPatch({ charm: e.target.checked })} /> end in .99</label>
          </>
        )}
      </div>
    </div>
  );
}
