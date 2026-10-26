import { useEffect, useLayoutEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessagesSquare, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { draftPitchScript, marketingKeys, startPitch, type JobStatus, type ScriptDraft } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { NeedsModel } from "@/features/settings/NeedsModel";

import { productNamedIn } from "./productMatch";
import type { Product } from "./products";

export function StaffPitchBuilder({ projectId, setupId, products, currency, personaCount, prefill, onPrefillHandled, onStarted }: {
  projectId: string; setupId: string; products: Product[]; currency: string; personaCount: number; onStarted: (job: JobStatus) => void;
  /** A request routed here from the command palette: used as the direction for script B, which is drafted at once. */
  prefill?: { text: string; id: number };
  onPrefillHandled?: (id: number) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [sku, setSku] = useState(products[0]?.sku ?? "");
  const [name, setName] = useState("");
  const [aName, setAName] = useState(() => t("mkPitchCurrentName"));
  const [bName, setBName] = useState(() => t("mkPitchAltName"));
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [context, setContext] = useState(() => t("mkPitchDefaultContext"));
  const [facts, setFacts] = useState("");
  const [panel, setPanel] = useState("40");
  const [seed, setSeed] = useState("1");
  const [model, setModel] = useState("");
  const count = Number(panel);
  const seedNumber = Number(seed);
  const normalize = (s: string) => s.trim().replace(/\s+/g, " ").toLowerCase();
  const sameScripts = !!a.trim() && normalize(a) === normalize(b);
  const sameNames = !!aName.trim() && aName.trim().toLowerCase() === bName.trim().toLowerCase();
  const validNumbers = panel.trim() !== "" && seed.trim() !== "" && Number.isInteger(count) && count >= 20 && count <= 500
    && Number.isInteger(seedNumber) && seedNumber >= 0 && seedNumber <= 2_147_483_647;
  const ready = products.some((p) => p.sku === sku) && personaCount >= 20 && validNumbers && a.trim() && b.trim()
    && context.trim() && aName.trim() && bName.trim() && !sameScripts && !sameNames;
  const run = useMutation({
    mutationFn: () => startPitch(projectId, {
      setup_id: setupId, sku, name: name.trim(), variants: [{ name: aName.trim(), script: a.trim() }, { name: bName.trim(), script: b.trim() }],
      context: context.trim(), product_facts: facts.trim(), panel: count, seed: seedNumber, model,
    }),
    onSuccess: async (job) => { await qc.invalidateQueries({ queryKey: marketingKeys.pitches(projectId) }); onStarted(job); },
  });
  // Script B drafted from script A: same product and offer, only the verified facts, a different approach.
  const [direction, setDirection] = useState("");
  const draftContext = JSON.stringify([projectId, setupId, currency, products, sku, context, facts, a, direction]);
  const [accepted, setAccepted] = useState<{ draft: ScriptDraft; context: string } | null>(null);
  const draft = useMutation({
    mutationFn: ({ dir, product }: { dir: string; product: string }) =>
      draftPitchScript(projectId, { setup_id: setupId, sku: product, context, product_facts: facts, current: a, direction: dir }),
  });
  const { reset } = draft;
  useLayoutEffect(() => reset(), [draftContext, b, bName, reset]);
  const requestDraft = (input: { dir: string; product: string }, replacePending = false) => {
    if (!products.some((p) => p.sku === input.product) || (draft.isPending && !replacePending)) return;
    draft.mutate(input, { onSuccess: (d) => {
      setAccepted({ draft: d, context: draftContext });
      setB(d.script);
      setBName(d.name);
    } });
  };
  const explanation = accepted?.context === draftContext && accepted.draft.script === b && accepted.draft.name === bName
    ? accepted.draft.differs_by : "";
  // A request routed from the command palette ("a friendlier pitch for the cold brew") picks the product it names.
  const prefillId = prefill?.id;
  const prefillText = prefill?.text;
  const queueDraft = useQueuedStart((input: { dir: string; product: string }) => requestDraft(input, true));
  const [handled, setHandled] = useState<number | null>(null);
  useEffect(() => {
    if (prefillId === undefined || !prefillText || handled === prefillId) return;
    setHandled(prefillId);  // only a new routed request drafts; later product or catalog changes do not
    const dir = Array.from(prefillText).slice(0, 200).join("");
    const named = productNamedIn(prefillText, products);
    if (named) setSku(named);
    setDirection(dir);
    queueDraft({ dir, product: named ?? sku });
    onPrefillHandled?.(prefillId);
  }, [prefillId, prefillText, queueDraft, handled, products, sku, onPrefillHandled]);
  return <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (ready) run.mutate(); }}>
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <h2 className="font-semibold">{t("mkPitchTitle")}</h2>
      <p className="text-sm text-muted-foreground">{t("mkPitchIntro")}</p>
      <label className="block space-y-1 text-sm">{t("mkPitchProduct")}
        <select aria-label={t("mkPitchProduct")} value={sku} onChange={(e) => setSku(e.target.value)} className="block h-10 w-full rounded-xl border bg-card px-2">
          {products.map((p) => <option key={p.sku} value={p.sku}>{p.name} · {formatMoney(p.price, currency)} · {p.sku}</option>)}
        </select>
      </label>
      <label className="block space-y-1 text-sm">{t("mkPitchContext")}
        <Textarea value={context} onChange={(e) => setContext(e.target.value)} maxLength={1200} required />
      </label>
      <label className="block space-y-1 text-sm">{t("mkPitchFacts")}
        <Textarea value={facts} onChange={(e) => setFacts(e.target.value)} maxLength={1600} placeholder={t("mkPitchFactsPlaceholder")} />
      </label>
      <p className="text-xs text-muted-foreground">{t("mkPitchPricesHint")}</p>
    </section>
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {([{ arm: "A", label: aName, setLabel: setAName, value: a, setValue: setA }, { arm: "B", label: bName, setLabel: setBName, value: b, setValue: setB }]).map((v) =>
        <section key={v.arm} className="space-y-3 rounded-2xl border bg-card p-4">
          <h3 className="font-semibold">{t("mkScriptN", { arm: v.arm })}</h3>
          <Input aria-label={t("mkScriptName", { arm: v.arm })} value={v.label} onChange={(e) => v.setLabel(e.target.value)} maxLength={40} required />
          <Textarea aria-label={t("mkScriptText", { arm: v.arm })} value={v.value} onChange={(e) => v.setValue(e.target.value)} maxLength={1200} rows={6} required
            placeholder={v.arm === "A" ? t("mkScriptAPlaceholder") : t("mkScriptBPlaceholder")} />
          <p className="text-xs text-muted-foreground">{t("mkScriptChars", { count: v.value.length })}</p>
          {v.arm === "B" && (
            <div className="space-y-1.5 border-t pt-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <Input aria-label={t("mkDirectionB")} value={direction} onChange={(e) => setDirection(Array.from(e.target.value).slice(0, 200).join(""))}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    e.preventDefault();
                    if (!e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) requestDraft({ dir: direction, product: sku });
                  }}
                  placeholder={t("mkDirectionPlaceholder")} className="h-8 min-w-[12rem] flex-1 text-xs" />
                <Button type="button" size="sm" variant="outline" disabled={!sku || draft.isPending} onClick={() => requestDraft({ dir: direction, product: sku })}>
                  {draft.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("mkWriteAlternative")}
                </Button>
              </div>
              {explanation && <p className="text-xs text-muted-foreground">{explanation} {t("mkSameOffer")}</p>}
              {draft.error && <p role="alert" className="text-xs text-destructive">{draft.error.message}</p>}
              {draft.error && <div className="basis-full"><NeedsModel purpose="assist" /></div>}
            </div>
          )}
        </section>)}
    </div>
    {(sameScripts || sameNames) && <p role="alert" className="text-sm text-destructive">{t("mkDistinctScripts")}</p>}
    <section className="grid grid-cols-1 gap-3 rounded-2xl border bg-card p-4 sm:grid-cols-2">
      <label className="space-y-1 text-sm">{t("mkRequestedShoppers")}
        <Input type="number" min={20} max={500} step={1} value={panel} onChange={(e) => setPanel(e.target.value)} required />
      </label>
      <label className="space-y-1 text-sm">{t("mkRandomSeed")}
        <Input type="number" min={0} max={2_147_483_647} step={1} value={seed} onChange={(e) => setSeed(e.target.value)} required />
      </label>
      <label className="space-y-1 text-sm">{t("mkTextModel")}
        <select value={model} onChange={(e) => setModel(e.target.value)} className="block h-10 w-full rounded-xl border bg-card px-2">
          <option value="">{t("studioAppTextModel")}</option>
          {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
        </select>
      </label>
      <label className="space-y-1 text-sm">{t("mkTestNameOptional")}
        <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
      </label>
      <p className="text-xs text-muted-foreground sm:col-span-2">{t("mkSavedPersonas", { count: personaCount })} {validNumbers ? t("mkPlannedRequests", { shoppers: Math.min(count, personaCount), requests: 2 * Math.min(count, personaCount) }) : t("mkChooseShoppersSeed")} {t("mkSavedWithTest")}</p>
    </section>
    {personaCount < 20 && <p role="alert" className="text-sm text-destructive">{t("mkNeedPersonas")}</p>}
    {run.error && <p role="alert" className="text-sm text-destructive">{run.error.message}</p>}
    <div className="flex justify-end"><Button type="submit" disabled={!ready || run.isPending}>
      {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <MessagesSquare className="size-4" />} {t("mkTestScripts")}
    </Button></div>
  </form>;
}
