// Concept test builder: up to four product images side by side (A–D), a short standard questionnaire, a quota of
// the project's personas, and a vision model that answers as each of them.

import { useEffect, useLayoutEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardList, Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { designSurvey, marketingKeys, startSurvey, type JobStatus, type QuestionKind, type SurveyDesign, type SurveyRequest } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { majorUnitText, minorUnitDivisor } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { modelLabel } from "@/shared/i18n/providerLabels";

import { usePackages } from "./hooks";
import { AGE_GROUPS as AGES, GENDERS, personaLabel } from "@/shared/i18n/personaLabels";
import { NeedsModel } from "@/features/settings/NeedsModel";
import { ProductDrop } from "./ProductLibrary";
import { toMinor } from "./products";
import { QUESTIONS } from "./questions";

const LETTERS = "ABCD";

export function SurveyBuilder({ projectId, personaCount, defaultCurrency = "USD", initial, setupId, prefill, onPrefillHandled, onStarted }: {
  projectId: string; personaCount: number; defaultCurrency?: string; initial?: SurveyRequest | null; setupId?: string;
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
  const [stimuli, setStimuli] = useState<string[]>(initial?.stimuli ?? []);
  const [names, setNames] = useState<Record<string, string>>(() =>
    Object.fromEntries((initial?.stimuli ?? []).map((id, i) => [id, initial?.stimulus_names[i] ?? ""]).filter(([, n]) => n)));
  const [questions, setQuestions] = useState<QuestionKind[]>(initial?.questions ?? ["purchase_intent", "appeal", "value", "preference", "open"]);
  const [context, setContext] = useState(initial?.context ?? "");
  const [currency, setCurrency] = useState(initial?.currency ?? defaultCurrency);
  const [price, setPrice] = useState(initial?.reference_price != null ? majorUnitText(initial.reference_price, initial.currency) : "");
  const [panel, setPanel] = useState(initial?.panel ?? 60);
  const [ages, setAges] = useState<string[]>(initial?.age_groups ?? []);
  const [genders, setGenders] = useState<string[]>(initial?.genders ?? []);
  const [model, setModel] = useState(initial?.model ?? "");
  const [name, setName] = useState(initial?.name ? Array.from(t("mkCopySuffix", { name: initial.name })).slice(0, 80).join("") : "");

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const pickStimulus = (id: string) => setStimuli((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 4 ? [...s, id] : s));
  const label = (id: string) => names[id] ?? packages.find((p) => p.asset_id === id)?.name ?? id;
  const asked = questions.filter((q) => q !== "preference" || stimuli.length > 1);
  const referencePrice = toMinor(price, minorUnitDivisor(currency));
  const invalidPrice = price.trim().length > 0 && referencePrice === null;

  // Draft the whole test from the question it should answer: images from the library, questions, brief, price,
  // quotas. Everything stays editable; images the library does not have are reported, not invented.
  const [question, setQuestion] = useState("");
  const questionLength = Array.from(question.trim()).length;
  const draftContext = JSON.stringify([projectId, setupId, defaultCurrency, packages]);
  const form = { question, stimuli, names, questions, context, currency, price, panel, ages, genders, model, name };
  const formKey = JSON.stringify(form);
  const [drafted, setDrafted] = useState<{ context: string; form: string; design: SurveyDesign } | null>(null);
  const draft = useMutation({
    mutationFn: (q: string) => designSurvey(projectId, { question: q.trim(), setup_id: setupId, currency }),
  });
  const { reset } = draft;
  useLayoutEffect(() => reset(), [draftContext, formKey, reset]);
  const requestDraft = (asked: string, replacePending = false) => {
    if (Array.from(asked.trim()).length < 5 || (draft.isPending && !replacePending)) return;
    draft.mutate(asked, { onSuccess: (d) => {
      const nextStimuli = d.stimuli.length > 0 ? d.stimuli : stimuli;
      const nextNames = d.stimuli.length > 0
        ? { ...names, ...Object.fromEntries(d.stimuli.map((id, i) => [id, d.stimulus_names[i] ?? ""]).filter(([, v]) => v)) }
        : names;
      const nextContext = d.context ? Array.from(d.context).slice(0, 300).join("") : context;
      const nextPrice = d.reference_price != null ? majorUnitText(d.reference_price, d.currency) : "";
      const nextName = name.trim() ? name : d.name;
      setStimuli(nextStimuli);
      setNames(nextNames);
      setQuestions(d.questions);
      setContext(nextContext);
      setCurrency(d.currency);
      setPrice(nextPrice);
      setAges(d.age_groups);
      setGenders(d.genders);
      setName(nextName);
      setDrafted({ context: draftContext, design: d, form: JSON.stringify({ ...form, question: asked,
        stimuli: nextStimuli, names: nextNames, questions: d.questions, context: nextContext,
        currency: d.currency, price: nextPrice, ages: d.age_groups, genders: d.genders, name: nextName }) });
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

  const run = useMutation({
    mutationFn: () => startSurvey(projectId, {
      name: name.trim(), stimuli, stimulus_names: stimuli.map(label), questions: asked, context: context.trim(), currency,
      reference_price: referencePrice, panel, age_groups: ages, genders, model,
    }),
    onSuccess: async (job) => {
      await qc.invalidateQueries({ queryKey: marketingKeys.surveys(projectId) });
      onStarted(job);
    },
  });

  return (
    <div className="space-y-4">
      <section className="glass space-y-3 rounded-2xl p-4">
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-foreground/[0.035] p-2">
          <Sparkles className="ml-1 size-4 shrink-0 text-primary" aria-hidden />
          <Input value={question} onChange={(e) => setQuestion(Array.from(e.target.value).slice(0, 500).join(""))}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229 && questionLength >= 5 && !draft.isPending) { e.preventDefault(); requestDraft(question); } }}
            placeholder={t("mkSurveyQuestionPlaceholder")}
            aria-label={t("mkSurveyQuestionLabel")} className="h-9 min-w-[14rem] flex-1 bg-card" />
          <Button type="button" size="sm" variant="outline" disabled={questionLength < 5 || draft.isPending} onClick={() => requestDraft(question)}>
            {draft.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {t("mkDraftTest")}
          </Button>
          {shownDraft && (
            <div className="basis-full space-y-0.5 px-1 text-xs text-muted-foreground">
              <p>{shownDraft.rationale} {t("mkCheckSurvey")}</p>
              {shownDraft.warnings.map((w) => <p key={w}>· {w}</p>)}
            </div>
          )}
          {draft.error && <p role="alert" className="basis-full px-1 text-xs text-destructive">{draft.error.message}</p>}
          {draft.error && <div className="basis-full"><NeedsModel purpose="assist" /></div>}
        </div>
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-semibold">{t("mkWhatTheySee")} <span className="font-normal text-muted-foreground">{t("mkWhatTheySeeHint")}</span></h3>
          <span className="num text-xs text-muted-foreground">{stimuli.length}/4</span>
        </div>
        <div className="flex flex-wrap items-stretch gap-2">
          {packages.map((p) => {
            const i = stimuli.indexOf(p.asset_id);
            return (
              <button key={p.asset_id} type="button" onClick={() => pickStimulus(p.asset_id)} title={p.name} aria-pressed={i >= 0}
                className={cn("relative flex h-28 w-24 items-center justify-center rounded-xl border bg-white p-1.5 transition-[box-shadow,border-color]",
                  i >= 0 ? "border-primary ring-2 ring-primary/40" : "hover:border-foreground/25")}>
                <img src={api.packageUrl(projectId, p.asset_id)} alt={p.name} className="max-h-full max-w-full object-contain" />
                {i >= 0 && <span className="absolute top-1 left-1 grid size-5 place-items-center rounded-md bg-primary text-[0.7rem] font-bold text-primary-foreground">{LETTERS[i]}</span>}
              </button>
            );
          })}
          <div className="w-64"><ProductDrop projectId={projectId} compact onUploaded={(a) => setStimuli((s) => [...s, ...a.map((x) => x.asset_id)].slice(0, 4))} /></div>
        </div>
        {stimuli.length > 0 && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {stimuli.map((id, i) => (
              <label key={id} className="flex items-center gap-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">{LETTERS[i]}</span>
                <Input value={label(id)} onChange={(e) => setNames((n) => ({ ...n, [id]: e.target.value }))} className="h-8 text-sm" maxLength={28} aria-label={t("mkNameOf", { letter: LETTERS[i]! })} />
              </label>
            ))}
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-[1.3fr_1fr]">
        <div className="rounded-2xl border bg-card p-4">
          <h3 className="mb-2 text-sm font-semibold">{t("mkQuestions")}</h3>
          <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            {QUESTIONS.map((q) => {
              const on = questions.includes(q.kind);
              const off = q.multi && stimuli.length < 2;
              return (
                <button key={q.kind} type="button" disabled={off} onClick={() => setQuestions((qs) => toggle(qs, q.kind))}
                  className={cn("flex items-start gap-2 rounded-xl border px-3 py-2 text-left transition-colors disabled:opacity-45",
                    on && !off ? "border-primary/70 bg-primary/[0.06]" : "hover:border-foreground/20")}>
                  <span className={cn("mt-0.5 grid size-4 shrink-0 place-items-center rounded border", on && !off ? "border-primary bg-primary text-primary-foreground" : "")}>
                    {on && !off && <Check className="size-3" />}
                  </span>
                  <span><b className="block text-sm">{t(q.label)}</b><span className="text-[0.7rem] text-muted-foreground">{off ? t("mkNeedsTwo") : t(q.hint)}</span></span>
                </button>
              );
            })}
          </div>
        </div>
        <div className="space-y-3 rounded-2xl border bg-card p-4">
          <h3 className="text-sm font-semibold">{t("mkBrief")}</h3>
          <Textarea value={context} onChange={(e) => setContext(Array.from(e.target.value).slice(0, 300).join(""))} rows={3}
            placeholder={t("mkBriefPlaceholder")} aria-label={t("mkBriefLabel")} />
          <div className="flex items-end gap-2">
            <label className="flex flex-1 flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t("mkShelfPriceA")}</span>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" placeholder="1.99" className="num h-9"
                aria-invalid={invalidPrice} aria-describedby={invalidPrice ? "survey-price-error" : undefined} />
            </label>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="h-9 rounded-xl border bg-card/60 px-2 text-sm" aria-label={t("mkCurrency")}>
              <option value="USD">USD</option><option value="EUR">EUR</option><option value="GBP">GBP</option><option value="KRW">KRW</option><option value="JPY">JPY</option>
            </select>
          </div>
          {invalidPrice && <p id="survey-price-error" className="text-xs text-destructive">{t("mkInvalidPriceBlank")}</p>}
          <div>
            <div className="flex items-baseline justify-between text-xs text-muted-foreground">
              <span>{t("mkPanelFromPersonas", { count: personaCount })}</span>
              <span className="num text-sm font-semibold text-foreground">{panel}</span>
            </div>
            <input type="range" min={5} max={400} step={5} value={panel} onChange={(e) => setPanel(Number(e.target.value))} className="w-full" aria-label={t("mkRespondents")} />
            <p className="text-[0.7rem] text-muted-foreground">{t("mkSurveyCalls", { count: panel })}</p>
          </div>
          <Chips label={t("studioAge")} options={AGES} value={ages} onToggle={(v) => setAges((a) => toggle(a, v))} />
          <Chips label={t("studioGender")} options={GENDERS} value={genders} onToggle={(v) => setGenders((g) => toggle(g, v))} />
          <select className="h-9 w-full rounded-xl border bg-card/60 px-2.5 text-sm" value={model} onChange={(e) => setModel(e.target.value)} aria-label={t("studioVisionModel")}>
            <option value="">{t("studioAppVisionModel")}</option>
            {models.filter((m) => m.vision).map((m) => <option key={m.ref} value={m.ref}>{modelLabel(m.ref, m.label, t)}</option>)}
          </select>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("mkTestNameOptional")} aria-label={t("mkTestNameOptional")} maxLength={80} className="mr-auto h-10 max-w-xs" />
        {run.error && <p role="alert" className="text-sm text-destructive">{run.error.message}</p>}
        <Button size="lg" disabled={stimuli.length === 0 || asked.length === 0 || invalidPrice || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <ClipboardList className="size-4" />}
          {t("mkFieldSurvey")}
        </Button>
        {run.error && <div className="basis-full"><NeedsModel /></div>}
      </div>
    </div>
  );
}

function Chips({ label, options, value, onToggle }: { label: string; options: string[]; value: string[]; onToggle: (v: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="w-14 text-xs text-muted-foreground">{label}</span>
      {options.map((o) => (
        <button key={o} type="button" onClick={() => onToggle(o)}
          className={cn("rounded-full border px-2.5 py-0.5 text-xs", value.includes(o) ? "border-primary bg-primary text-primary-foreground" : "hover:border-foreground/25")}>
          {personaLabel(o, t)}
        </button>
      ))}
      {value.length === 0 && <span className="text-[0.7rem] text-muted-foreground">{t("studioAll")}</span>}
    </div>
  );
}
