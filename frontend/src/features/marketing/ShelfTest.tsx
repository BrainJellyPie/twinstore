// Virtual shelf test: respondents stand in front of one shelf face twice — as it is and with a change to one
// product (new pack, price, sign) — pick what they would take and name what caught their eye first.

import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Rows3, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import {
  designShelfTest,
  marketingKeys,
  previewShelf,
  shelfTestImageUrl,
  shelfTestReportUrl,
  startShelfTest,
  type JobStatus,
  type ShelfTestDesign,
  type ShelfTestReport as Report,
  type ShelfTestRequest,
  type VariantChange,
} from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import type { Store } from "@/shared/types/domain";
import { cn } from "@/shared/utils/cn";
import { formatMoney, majorUnitText, minorUnitDivisor } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { LiftChart } from "./charts";
import { usePackages } from "./hooks";
import { AGE_GROUPS as AGES, personaLabel } from "@/shared/i18n/personaLabels";
import { NeedsModel } from "@/features/settings/NeedsModel";
import { toMinor } from "./products";
import { StudyReading } from "./StudyReading";
import { TestOnline } from "./TestOnline";

const PROMOS = ["", "NEW", "SALE", "1+1", "-20%"];
const ARM_LABEL: Record<"control" | "test", MessageKey> = { control: "mkArmControl", test: "mkArmTest" };

export function ShelfTestBuilder({ projectId, setupId, store, currency, initial, prefill, onPrefillHandled, onStarted }: {
  projectId: string; setupId: string; store: Store; currency: string; initial?: ShelfTestRequest | null;
  /** A request routed from the command palette: fills the question and drafts the test from it. */
  prefill?: { text: string; id: number };
  /** Called once the routed request has been taken, so the page can forget it. */
  onPrefillHandled?: (id: number) => void;
  onStarted: (job: JobStatus) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const packages = usePackages(projectId).data ?? [];
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const racks = useMemo(() => store.racks.filter((r) => r.slots.some((s) => s.items.length)), [store]);
  const [rackId, setRackId] = useState(initial?.rack_id ?? racks[0]?.id ?? "");
  const rack = racks.find((r) => r.id === rackId);
  const items = useMemo(() => {
    const seen = new Map<string, { sku: string; name: string; price: number }>();
    for (const s of rack?.slots ?? []) for (const i of s.items) if (!seen.has(i.sku)) seen.set(i.sku, { sku: i.sku, name: i.name, price: i.price });
    return [...seen.values()];
  }, [rack]);
  const [target, setTarget] = useState(initial?.target_sku ?? "");
  const product = items.find((i) => i.sku === target);
  const init = (kind: VariantChange["kind"]) => initial?.changes.find((c) => c.kind === kind);
  const [assetId, setAssetId] = useState(init("package")?.asset_id ?? "");
  const divisor = minorUnitDivisor(currency);
  const [priceText, setPriceText] = useState(init("price")?.price != null ? majorUnitText(init("price")!.price!, currency, { fixed: true }) : "");
  const [promo, setPromo] = useState(init("promo")?.promo ?? "");
  const [panel, setPanel] = useState(initial?.panel ?? 60);
  const [ages, setAges] = useState<string[]>(initial?.age_groups ?? []);
  const [model, setModel] = useState(initial?.model ?? "");
  const [name, setName] = useState(initial?.name ? t("mkCopySuffix", { name: initial.name }) : "");

  const price = toMinor(priceText, divisor);
  const invalidPrice = priceText.trim() !== "" && price === null;
  const changes: VariantChange[] = [
    ...(assetId ? [{ kind: "package" as const, sku: target, asset_id: assetId }] : []),
    ...(price !== null ? [{ kind: "price" as const, sku: target, price, keep_reference: true }] : []),
    ...(promo ? [{ kind: "promo" as const, sku: target, promo }] : []),
  ];
  // Live preview of both shelves, refreshed shortly after the last edit.
  const previewBody = JSON.stringify({ setup_id: setupId, rack_id: rackId, target_sku: target, changes });
  const [debounced, setDebounced] = useState(previewBody);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(previewBody), 350);
    return () => window.clearTimeout(t);
  }, [previewBody]);
  const preview = useQuery({
    queryKey: ["projects", projectId, "shelf-preview", debounced],
    queryFn: ({ signal }) => previewShelf(projectId, JSON.parse(debounced) as Parameters<typeof previewShelf>[1], signal),
    enabled: !!rackId && !invalidPrice,
    placeholderData: (prev) => prev,
    staleTime: 60_000,
  });
  // Draft the test from the question it should answer: the product and its shelf, and the pack, price or sign
  // respondents see on the test shelf. Everything stays editable.
  const [question, setQuestion] = useState("");
  const questionLength = Array.from(question.trim()).length;
  const draftContext = JSON.stringify([projectId, setupId, currency, store, packages]);
  const form = { question, rackId, target, assetId, priceText, promo, panel, ages, model, name };
  const formKey = JSON.stringify(form);
  const [drafted, setDrafted] = useState<{ context: string; form: string; design: ShelfTestDesign } | null>(null);
  const draft = useMutation({
    mutationFn: (q: string) => designShelfTest(projectId, { question: q.trim(), setup_id: setupId }),
  });
  const { reset } = draft;
  useLayoutEffect(() => reset(), [draftContext, formKey, reset]);
  const requestDraft = (asked: string, replacePending = false) => {
    if (Array.from(asked.trim()).length < 5 || (draft.isPending && !replacePending)) return;
    draft.mutate(asked, { onSuccess: (d) => {
      const change = (kind: VariantChange["kind"]) => d.changes.find((c) => c.kind === kind);
      const nextAsset = change("package")?.asset_id ?? "";
      const p = change("price")?.price;
      const nextPrice = p != null ? majorUnitText(p, currency, { fixed: true }) : "";
      const nextPromo = change("promo")?.promo ?? "";
      const nextName = name.trim() ? name : d.name;
      setRackId(d.rack_id);
      setTarget(d.target_sku);
      setAssetId(nextAsset);
      setPriceText(nextPrice);
      setPromo(nextPromo);
      setAges(d.age_groups);
      setName(nextName);
      setDrafted({ context: draftContext, design: d, form: JSON.stringify({ ...form, question: asked,
        rackId: d.rack_id, target: d.target_sku, assetId: nextAsset, priceText: nextPrice,
        promo: nextPromo, ages: d.age_groups, name: nextName }) });
    } });
  };
  const queueDraft = useQueuedStart((asked: string) => requestDraft(asked, true));
  const prefillId = prefill?.id;
  const prefillText = prefill?.text;
  useEffect(() => {
    if (prefillId === undefined || !prefillText) return;
    const text = Array.from(prefillText).slice(0, 500).join("");
    setQuestion(text);
    queueDraft(text);
    onPrefillHandled?.(prefillId);
  }, [prefillId, prefillText, queueDraft, onPrefillHandled]);
  const shownDraft = drafted?.context === draftContext && drafted.form === formKey ? drafted.design : null;
  const promos = promo && !PROMOS.includes(promo) ? [...PROMOS, promo] : PROMOS;

  const run = useMutation({
    mutationFn: () => startShelfTest(projectId, { name: name.trim(), setup_id: setupId, rack_id: rackId, target_sku: target, changes, panel, age_groups: ages, model }),
    onSuccess: async (job) => {
      await qc.invalidateQueries({ queryKey: marketingKeys.shelfTests(projectId) });
      onStarted(job);
    },
  });

  return (
    <div className="space-y-4">
      <section className="glass grid grid-cols-1 gap-3 rounded-2xl p-4 md:grid-cols-2">
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-foreground/[0.035] p-2 md:col-span-2">
          <Sparkles className="ml-1 size-4 shrink-0 text-primary" aria-hidden />
          <Input value={question} onChange={(e) => setQuestion(Array.from(e.target.value).slice(0, 500).join(""))}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229 && questionLength >= 5 && !draft.isPending) { e.preventDefault(); requestDraft(question); } }}
            placeholder={t("mkShelfQuestionPlaceholder")}
            aria-label={t("mkShelfQuestionLabel")} className="h-9 min-w-0 grow basis-56 bg-card" />
          <Button type="button" size="sm" variant="outline" disabled={questionLength < 5 || draft.isPending} onClick={() => requestDraft(question)}>
            {draft.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("mkDraftTest")}
          </Button>
          {shownDraft && (
            <div className="basis-full space-y-0.5 px-1 text-xs text-muted-foreground">
              <p>{shownDraft.rationale} {t("mkCheckShelf")}</p>
              {shownDraft.warnings.map((w) => <p key={w}>· {w}</p>)}
            </div>
          )}
          {draft.error && <p role="alert" className="basis-full px-1 text-xs text-destructive">{draft.error.message}</p>}
          {draft.error && <div className="basis-full"><NeedsModel purpose="assist" /></div>}
        </div>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">{t("mkShelf")}</span>
          <select value={rackId} onChange={(e) => { setRackId(e.target.value); setTarget(""); }} className="h-10 rounded-xl border bg-card/60 px-2.5 text-sm">
            {racks.map((r) => <option key={r.id} value={r.id}>{r.rack_name || r.id}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">{t("mkProductUnderTest")}</span>
          <select value={target} onChange={(e) => setTarget(e.target.value)} className="h-10 rounded-xl border bg-card/60 px-2.5 text-sm">
            <option value="">{t("mkChooseShelfProduct")}</option>
            {items.map((i) => <option key={i.sku} value={i.sku}>{i.name} · {formatMoney(i.price, currency)}</option>)}
          </select>
        </label>
        <p className="text-xs text-muted-foreground md:col-span-2">
          {t("mkShelfIntro")} {rack ? t("mkShelfProductsOn", { count: items.length, name: rack.rack_name || t("mkThisShelf") }) : ""}
        </p>
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkNewPack")}</h3>
          <div className="flex flex-wrap gap-1.5">
            <button type="button" onClick={() => setAssetId("")}
              className={cn("h-16 rounded-lg border px-2 text-[0.7rem]", !assetId ? "border-primary text-foreground" : "text-muted-foreground")}>{t("mkCurrent1")}<br />{t("mkCurrent2")}</button>
            {packages.map((p) => (
              <button key={p.asset_id} type="button" title={p.name} onClick={() => setAssetId(p.asset_id)}
                className={cn("flex size-16 items-center justify-center overflow-hidden rounded-lg border bg-white p-1", assetId === p.asset_id ? "border-primary ring-2 ring-primary/40" : "hover:border-foreground/25")}>
                <img src={api.packageUrl(projectId, p.asset_id)} alt={p.name} className="max-h-full max-w-full object-contain" />
              </button>
            ))}
          </div>
          {packages.length === 0 && <p className="mt-2 text-xs text-muted-foreground">{t("mkAddPackImages")}</p>}
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkPrice")}</h3>
          <Input value={priceText} onChange={(e) => setPriceText(e.target.value)} inputMode="decimal"
            placeholder={product ? t("mkNowKeep", { price: formatMoney(product.price, currency) }) : t("mkLeaveEmpty")} className="num h-9" />
          <p className="mt-2 text-xs text-muted-foreground">{t("mkShelfPriceHint")}</p>
        </div>
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkSign")}</h3>
          <div className="flex flex-wrap gap-1.5">
            {promos.map((p) => (
              <button key={p || "none"} type="button" onClick={() => setPromo(p)}
                className={cn("rounded-full border px-2.5 py-0.5 text-xs font-semibold", promo === p ? (p ? "border-transparent bg-[#e8182e] text-white" : "border-primary") : "hover:border-foreground/25")}>
                {p || t("studioNone")}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="glass grid gap-4 rounded-2xl p-4 lg:grid-cols-3">
        <div>
          <div className="flex items-baseline justify-between text-xs text-muted-foreground"><span>{t("mkRespondentsBoth")}</span><span className="num text-sm font-semibold text-foreground">{panel}</span></div>
          <input type="range" min={10} max={300} step={10} value={panel} onChange={(e) => setPanel(Number(e.target.value))} className="w-full" aria-label={t("mkRespondents")} />
          <p className="text-[0.7rem] text-muted-foreground">{t("mkVisionCalls", { count: panel * 2 })}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="w-10 text-xs text-muted-foreground">{t("studioAge")}</span>
          {AGES.map((a) => (
            <button key={a} type="button" onClick={() => setAges((x) => (x.includes(a) ? x.filter((y) => y !== a) : [...x, a]))}
              className={cn("rounded-full border px-2 py-0.5 text-xs", ages.includes(a) ? "border-primary bg-primary text-primary-foreground" : "hover:border-foreground/25")}>{personaLabel(a, t)}</button>
          ))}
          {ages.length === 0 && <span className="text-[0.7rem] text-muted-foreground">{t("studioAll")}</span>}
        </div>
        <select value={model} onChange={(e) => setModel(e.target.value)} className="h-9 rounded-xl border bg-card/60 px-2.5 text-sm" aria-label={t("studioVisionModel")}>
          <option value="">{t("studioAppVisionModel")}</option>
          {models.filter((m) => m.vision).map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
        </select>
      </section>

      {preview.data && (
        <section className={cn("grid grid-cols-1 gap-3 md:grid-cols-2", preview.isFetching && "opacity-70 transition-opacity")}>
          {(["control", "test"] as const).map((arm) => (
            <figure key={arm} className="overflow-hidden rounded-2xl border bg-card">
              <img src={preview.data[arm]} alt={t("mkShelfPreviewAlt", { arm: t(ARM_LABEL[arm]) })} className="w-full" />
              <figcaption className="px-3 py-2 text-xs text-muted-foreground">
                <b className="text-foreground">{arm === "control" ? t("mkControlAsIs") : t("mkTestSees")}</b>{t("mkFaceSide", { face: preview.data.face })}
                {arm === "test" && preview.data.applied.length > 0 ? ` · ${preview.data.applied.join("; ")}` : ""}
              </figcaption>
            </figure>
          ))}
        </section>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("mkTestNameOptional")} maxLength={80} className="mr-auto h-10 max-w-xs" />
        {!target && <span className="text-sm text-muted-foreground">{t("mkChooseUnderTest")}</span>}
        {target && changes.length === 0 && <span className="text-sm text-muted-foreground">{t("mkChangeSomething")}</span>}
        {invalidPrice && <p role="alert" className="text-sm text-destructive">{t("mkInvalidPriceCurrent")}</p>}
        {preview.error && <p role="alert" className="text-sm text-destructive">{preview.error.message}</p>}
        {run.error && <p role="alert" className="text-sm text-destructive">{run.error.message}</p>}
        <Button size="lg" disabled={!target || invalidPrice || changes.length === 0 || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Rows3 className="size-4" />} {t("mkRunShelf")}
        </Button>
        {run.error && <div className="basis-full"><NeedsModel /></div>}
      </div>
    </div>
  );
}

const METRIC: Record<string, MessageKey> = { pick: "mkMetricPick", noticed: "mkMetricNoticed", noticed_first: "mkMetricNoticedFirst" };

export function ShelfTestReportView({ projectId, report: r, changes = [] }: {
  projectId: string; report: Report;
  /** The tested changes (from the request), to try in an online store. */
  changes?: VariantChange[];
}) {
  const { t } = useI18n();
  const pick = r.comparisons.find((c) => c.metric === "pick");
  const pctf = (v: number) => `${(v * 100).toFixed(0)}%`;
  const pp = (v: number) => t("studioPt", { value: `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(1)}` });
  const why = r.choices.filter((c) => c.arm === "test" && c.pick_sku === r.target_sku && c.why).slice(0, 8);
  const verdict = pick ? (pick.ci_low > 0 ? "more" : pick.ci_high < 0 ? "fewer" : null) : null;
  const topShare = Math.max(0.01, ...r.picks.flatMap((p) => [p.control, p.test]));
  return (
    <div className="space-y-4">
      <div className={cn("flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3 text-sm", verdict === "more" ? "tone-good" : verdict === "fewer" ? "tone-bad" : "bg-foreground/[0.03]")}>
        <span className="min-w-0 flex-1">{pick ? (
          verdict
            ? <><b>{t(verdict === "more" ? "mkVerdictMore" : "mkVerdictFewer", { name: r.target_name })}</b>{t("mkVerdictDetail", { control: pctf(pick.control), test: pctf(pick.test), diff: pp(pick.diff), low: pp(pick.ci_low), high: pp(pick.ci_high) })}</>
            : t("mkVerdictNone", { name: r.target_name, control: pctf(pick.control), test: pctf(pick.test), low: pp(pick.ci_low), high: pp(pick.ci_high) })
        ) : t("mkNoPairedAnswers")}</span>
        <Button asChild size="sm" variant="outline"><a href={shelfTestReportUrl(projectId, r.test_id)} target="_blank" rel="noopener"><FileText className="size-4" /> {t("studioReport")}</a></Button>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {(["control", "test"] as const).map((arm) => (
          <figure key={arm} className="overflow-hidden rounded-2xl border bg-card">
            <img src={shelfTestImageUrl(projectId, r.test_id, arm)} alt={t("mkShelfAlt", { arm: t(ARM_LABEL[arm]) })} className="w-full" />
            <figcaption className="px-3 py-2 text-xs text-muted-foreground">
              <b className="text-foreground">{arm === "control" ? t("mkControlCap") : t("mkTestCap")}</b> · {r.rack_name}{t("mkFaceSide", { face: r.face })}{arm === "test" ? ` · ${r.applied.join("; ")}` : ""}
            </figcaption>
          </figure>
        ))}
      </div>
      {changes.length > 0 && <TestOnline projectId={projectId} testName={r.name} currency={r.currency}
        variant={{ name: r.target_name || r.name, changes }} />}
      <StudyReading projectId={projectId} study="shelf-tests" jobId={r.test_id} answers={r.choices.filter((c) => c.why && !c.error).length} />
      <section className="rounded-2xl border bg-card p-4">
        <h3 className="text-sm font-semibold">{t("mkTestVsControl", { name: r.target_name })}</h3>
        <p className="mb-3 text-xs text-muted-foreground">{t("mkShelfLiftHint", { count: r.respondents })}</p>
        <LiftChart format={pp} axisLabel={t("mkShareOfRespondents")}
          rows={r.comparisons.map((c) => ({ key: c.metric, label: METRIC[c.metric] ? t(METRIC[c.metric]!) : c.metric, sub: `${pctf(c.control)} → ${pctf(c.test)}`, diff: c.diff, lo: c.ci_low, hi: c.ci_high, detail: t("mkPHigherTest", { pct: Math.round(c.prob_better * 100) }) }))} />
      </section>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkWhatTheyTake")}</h3>
          <div className="space-y-1.5">
            {r.picks.map((p) => (
              <div key={p.sku || "none"} className="grid grid-cols-[minmax(6rem,10rem)_1fr_5.5rem] items-center gap-2 text-xs">
                <span className={cn("truncate", p.sku === r.target_sku && "font-semibold")}>{p.name}</span>
                <div className="space-y-0.5">
                  <div className="h-2 rounded-r-[4px] bg-foreground/[0.18]" style={{ width: `${Math.max(1, (p.control / topShare) * 100)}%` }} title={t("mkControlPct", { pct: pctf(p.control) })} />
                  <div className="h-2 rounded-r-[4px]" style={{ width: `${Math.max(1, (p.test / topShare) * 100)}%`, background: "var(--viz-1)" }} title={t("mkTestPct", { pct: pctf(p.test) })} />
                </div>
                <span className="num text-right text-muted-foreground">{pctf(p.control)} → <b className="text-foreground">{pctf(p.test)}</b></span>
              </div>
            ))}
          </div>
          <p className="mt-2 flex gap-3 text-[0.7rem] text-muted-foreground">
            <span className="inline-flex items-center gap-1"><span className="h-2 w-3 rounded-sm bg-foreground/[0.18]" /> {t("mkArmControl")}</span>
            <span className="inline-flex items-center gap-1"><span className="h-2 w-3 rounded-sm" style={{ background: "var(--viz-1)" }} /> {t("mkArmTest")}</span>
          </p>
        </section>
        <section className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkWhyTook", { name: r.target_name })}</h3>
          {why.length ? (
            <ul className="space-y-1.5">{why.map((c) => <li key={c.respondent} className="rounded-xl bg-foreground/[0.035] px-3 py-1.5 text-sm">{c.why} <span className="text-[0.7rem] text-muted-foreground">· {personaLabel(c.age_group, t)}</span></li>)}</ul>
          ) : <p className="text-sm text-muted-foreground">{t("mkNobodyPicked")}</p>}
        </section>
      </div>
      <footer className="space-y-1 text-xs text-muted-foreground">
        <p>{t("mkRespondentsCount", { count: r.respondents })}{r.errors ? t("mkFailedAnswers", { count: r.errors }) : ""} · {r.model} · {r.seconds}s</p>
        {r.warnings.map((w) => <p key={w}>⚠ {w}</p>)}
        {r.notes.map((n) => <p key={n}>{n}</p>)}
      </footer>
    </div>
  );
}
