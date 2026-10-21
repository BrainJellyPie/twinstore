// Conjoint builder: the product, its attributes and levels, price levels, the choice-task design, and the
// respondents. A sample task shows what one respondent will be asked.

import { useLayoutEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Dices, Grid3x3, Loader2, Plus, Sparkles, X } from "lucide-react";

import * as api from "@/shared/api/client";
import { designConjoint, marketingKeys, startConjoint, type ConjointDesign, type ConjointRequest, type JobStatus } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { formatMoney, minorUnitDivisor, toMinor } from "@/shared/utils/money";

const AGES = ["10s", "20s", "30s", "40s", "50s", "60s+"];
const GENDERS = ["Female", "Male"];
const LETTERS = "ABCD";

interface Draft { name: string; levels: string }

const EXAMPLES: { label: string; product: string; attributes: Draft[]; prices: string }[] = [
  {
    label: "Iced tea", product: "a bottle of iced tea", prices: "1.49, 1.79, 1.99, 2.29",
    attributes: [
      { name: "Sugar", levels: "Regular, Less sugar, Zero sugar" },
      { name: "Size", levels: "330 ml, 500 ml, 1 L" },
      { name: "Brand", levels: "Store brand, Known brand" },
    ],
  },
  {
    label: "Ready meal", product: "a chilled ready meal for one", prices: "3.99, 4.99, 5.99",
    attributes: [
      { name: "Dish", levels: "Pasta, Rice bowl, Salad" },
      { name: "Claim", levels: "None, High protein, Organic" },
      { name: "Pack", levels: "Plastic tray, Paper tray" },
    ],
  },
];

// Rough size of one US dollar in currencies whose prices have no minor unit, for the example price levels; other
// zero-decimal currencies get no example prices rather than wrong ones.
const DOLLAR_IN: Record<string, number> = { KRW: 1000, JPY: 100 };

const splitLevels = (text: string) => text.split(",").map((l) => l.trim()).filter(Boolean);

/** Levels for one sample task, like the real design: shuffled, and no level twice while others are unused. */
function sampleColumn(n: number, options: number, seed: number): number[] {
  let s = seed >>> 0 || 1;
  const order = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    const j = (s >>> 8) % (i + 1);
    [order[i], order[j]] = [order[j]!, order[i]!];
  }
  return Array.from({ length: options }, (_, o) => order[o % n]!);
}

export function ConjointBuilder({ projectId, personaCount, defaultCurrency = "USD", initial, setupId, onStarted }: {
  projectId: string; personaCount: number; defaultCurrency?: string; initial?: ConjointRequest | null;
  /** A layout in the study's currency: drafted price levels bracket its comparable products. */
  setupId?: string;
  onStarted: (job: JobStatus) => void;
}) {
  const qc = useQueryClient();
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const currency = initial?.currency ?? defaultCurrency;
  const divisor = minorUnitDivisor(currency);
  const [product, setProduct] = useState(initial?.product ?? "");
  const [context, setContext] = useState(initial?.context ?? "");
  const [attrs, setAttrs] = useState<Draft[]>(initial?.attributes.map((a) => ({ name: a.name, levels: a.levels.join(", ") }))
    ?? [{ name: "", levels: "" }, { name: "", levels: "" }]);
  const [priceText, setPriceText] = useState(initial?.prices.map((p) => String(p / divisor)).join(", ") ?? "");
  const [tasks, setTasks] = useState(initial?.tasks ?? 8);
  const [options, setOptions] = useState(initial?.options ?? 3);
  const [none, setNone] = useState(initial?.none_option ?? true);
  const [panel, setPanel] = useState(initial?.panel ?? 60);
  const [ages, setAges] = useState<string[]>(initial?.age_groups ?? []);
  const [genders, setGenders] = useState<string[]>(initial?.genders ?? []);
  const [model, setModel] = useState(initial?.model ?? "");
  const [name, setName] = useState(initial?.name ? Array.from(`${initial.name} (copy)`).slice(0, 80).join("") : "");
  const [roll, setRoll] = useState(1);

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const parsed = attrs.map((a) => ({ name: a.name.trim(), levels: splitLevels(a.levels) }));
  const priceParts = splitLevels(priceText);
  const prices = priceParts.map((p) => toMinor(p, divisor));
  const validPrices = prices.filter((p): p is number => p !== null);

  const problems: string[] = [];
  if (!product.trim()) problems.push("Say what respondents are choosing.");
  parsed.forEach((a, i) => {
    if (!a.name) problems.push(`Attribute ${i + 1} needs a name.`);
    else if (a.levels.length < 2 || a.levels.length > 6) problems.push(`${a.name}: give 2–6 levels, separated by commas.`);
    else if (new Set(a.levels.map((l) => l.toLowerCase())).size !== a.levels.length) problems.push(`${a.name}: levels must differ.`);
  });
  const names = parsed.map((a) => a.name.toLowerCase()).filter(Boolean);
  if (new Set(names).size !== names.length) problems.push("Give each attribute a different name.");
  if (priceParts.length && names.includes("price")) problems.push("Prices have their own row; rename the 'Price' attribute.");
  if (validPrices.length !== priceParts.length) problems.push("Price levels must be amounts like 1.99.");
  else if (priceParts.length === 1 || priceParts.length > 6) problems.push("Give 2–6 price levels, or none.");
  else if (new Set(validPrices).size !== validPrices.length) problems.push("Price levels must differ.");
  if (parsed.length + (priceParts.length ? 1 : 0) < 2) problems.push("Use at least two attributes, counting price.");

  const profiles = parsed.reduce((n, a) => n * Math.max(1, a.levels.length), 1) * Math.max(1, validPrices.length);
  const levelCounts = [...parsed.map((a) => a.levels.length), validPrices.length];
  const columns = levelCounts.map((n, k) => (n ? sampleColumn(n, options, roll * 7919 + k * 104729) : []));
  const shown = new Set<string>();
  const sample = Array.from({ length: options }, (_, o) => {
    let profile = columns.map((column) => column[o] ?? 0);
    // At most o prior profiles can block candidates; incomplete drafts may have fewer combinations.
    for (let candidate = 0; shown.has(profile.join(",")) && candidate <= o; candidate++) {
      let remaining = candidate;
      const alternative = levelCounts.map((count) => {
        const n = Math.max(1, count);
        const level = remaining % n;
        remaining = Math.floor(remaining / n);
        return level;
      });
      if (remaining === 0 && !shown.has(alternative.join(","))) profile = alternative;
    }
    shown.add(profile.join(","));
    return [
      ...parsed.map((a, k) => (a.levels.length ? `${a.name || "Attribute"}: ${a.levels[profile[k]!]}` : "")).filter(Boolean),
      ...(validPrices.length ? [`Price: ${formatMoney(validPrices[profile[parsed.length]!]!, currency)}`] : []),
    ];
  });

  const run = useMutation({
    mutationFn: () => startConjoint(projectId, {
      name: name.trim(), product: product.trim(), context: context.trim(), attributes: parsed, prices: validPrices, currency,
      tasks, options, none_option: none, panel, age_groups: ages, genders, model,
    }),
    onSuccess: async (job) => {
      await qc.invalidateQueries({ queryKey: marketingKeys.conjoints(projectId) });
      onStarted(job);
    },
  });

  const applyExample = (e: (typeof EXAMPLES)[number]) => {
    setProduct(e.product);
    setAttrs(e.attributes);
    const factor = divisor === 1 ? DOLLAR_IN[currency.toUpperCase()] : 1;
    setPriceText(!factor ? "" : factor === 1 ? e.prices : splitLevels(e.prices).map((p) => String(Math.round((Number(p) * factor) / 10) * 10)).join(", "));
  };

  // Draft the whole design from the question the study should answer.
  const [question, setQuestion] = useState("");
  const questionLength = Array.from(question.trim()).length;
  const [accepted, setAccepted] = useState<{
    design: ConjointDesign; question: string; projectId: string; setupId?: string; currency: string;
  } | null>(null);
  const draft = useMutation({
    mutationFn: () => designConjoint(projectId, { question: question.trim(), setup_id: setupId, currency }),
  });
  const resetDraft = draft.reset;
  // A reply belongs to the question and editable design from which it was requested.
  useLayoutEffect(() => {
    resetDraft();
  }, [question, projectId, setupId, currency, product, context, attrs, priceText, name, resetDraft]);
  const requestDraft = () => draft.mutate(undefined, {
    onSuccess: (d) => {
      setAccepted({ design: d, question, projectId, setupId, currency });
      setProduct(d.product);
      setContext(d.context);
      setAttrs(d.attributes.map((a) => ({ name: a.name, levels: a.levels.join(", ") })));
      setPriceText(d.prices.map((p) => String(p / divisor)).join(", "));
      if (!name.trim()) setName(d.name);
    },
  });
  const designed = accepted?.question === question && accepted.projectId === projectId
    && accepted.setupId === setupId && accepted.currency === currency ? accepted.design : null;

  return (
    <div className="space-y-4">
      <section className="glass space-y-3 rounded-2xl p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">Product and attributes <span className="font-normal text-muted-foreground">· levels separated by commas; the first level is the base for willingness to pay</span></h3>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            Example
            {EXAMPLES.map((e) => (
              <button key={e.label} type="button" onClick={() => applyExample(e)} className="rounded-full border px-2.5 py-0.5 text-xs text-foreground hover:border-foreground/30">{e.label}</button>
            ))}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-foreground/[0.035] p-2">
          <Sparkles className="ml-1 size-4 shrink-0 text-primary" aria-hidden />
          <Input value={question} onChange={(e) => setQuestion(Array.from(e.target.value).slice(0, 500).join(""))}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229 && questionLength >= 5 && !draft.isPending) { e.preventDefault(); requestDraft(); } }}
            placeholder="What should the study answer? e.g. Would shoppers pay more for zero-sugar tea in a bigger bottle?"
            aria-label="Question for the study" className="h-9 min-w-[14rem] flex-1 bg-card" />
          <Button type="button" size="sm" variant="outline" disabled={questionLength < 5 || draft.isPending} onClick={requestDraft}>
            {draft.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Draft the study
          </Button>
          {designed && (
            <p className="basis-full px-1 text-xs text-muted-foreground">
              {designed.rationale}
              {designed.comparable.length > 0 && <> Prices set against {designed.comparable.join(", ")}.</>}
              {" "}Check and edit everything below before starting.
            </p>
          )}
          {draft.error && <p role="alert" className="basis-full px-1 text-xs text-destructive">{draft.error.message}</p>}
        </div>
        <div className="grid gap-2 sm:grid-cols-[1fr_1.4fr]">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Respondents are choosing…</span>
            <Input value={product} onChange={(e) => setProduct(Array.from(e.target.value).slice(0, 160).join(""))} placeholder="a bottle of iced tea" className="h-9" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Anything else they are told (optional)</span>
            <Input value={context} onChange={(e) => setContext(Array.from(e.target.value).slice(0, 300).join(""))} placeholder="Sold in the drinks fridge next to the sodas." className="h-9" />
          </label>
        </div>
        <div className="space-y-2">
          {attrs.map((a, i) => {
            const levels = splitLevels(a.levels);
            return (
              <div key={i} className="grid items-center gap-2 sm:grid-cols-[11rem_1fr_auto]">
                <Input value={a.name} onChange={(e) => setAttrs((xs) => xs.map((x, j) => (j === i ? { ...x, name: Array.from(e.target.value).slice(0, 40).join("") } : x)))}
                  placeholder={`Attribute ${i + 1}`} aria-label={`Attribute ${i + 1} name`} className="h-9 font-medium" />
                <div className="relative">
                  <Input value={a.levels} onChange={(e) => setAttrs((xs) => xs.map((x, j) => (j === i ? { ...x, levels: e.target.value } : x)))}
                    placeholder="Regular, Less sugar, Zero sugar" aria-label={`Levels of ${a.name || `attribute ${i + 1}`}`} className="h-9 pr-14" />
                  <span className={cn("num absolute top-1/2 right-3 -translate-y-1/2 text-[0.7rem]", levels.length >= 2 && levels.length <= 6 ? "text-muted-foreground" : "text-destructive")}>
                    {levels.length} lvl
                  </span>
                </div>
                <button type="button" disabled={attrs.length <= 1} onClick={() => setAttrs((xs) => xs.filter((_, j) => j !== i))} aria-label={`Remove ${a.name || `attribute ${i + 1}`}`}
                  className="rounded-md p-1.5 text-muted-foreground hover:text-destructive disabled:opacity-30">
                  <X className="size-4" />
                </button>
              </div>
            );
          })}
          <div className="grid items-center gap-2 sm:grid-cols-[11rem_1fr_auto]">
            <span className="px-3 text-sm font-medium">Price <span className="text-xs font-normal text-muted-foreground">({currency})</span></span>
            <Input value={priceText} onChange={(e) => setPriceText(e.target.value)} placeholder="1.49, 1.79, 1.99 (optional)" inputMode="decimal" aria-label="Price levels" className="num h-9" />
            <span className="w-7" />
          </div>
          {attrs.length < 6 && (
            <button type="button" onClick={() => setAttrs((xs) => [...xs, { name: "", levels: "" }])}
              className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-foreground/[0.05] hover:text-foreground">
              <Plus className="size-3.5" /> Add attribute
            </button>
          )}
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-3 rounded-2xl border bg-card p-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-sm font-semibold">A sample choice task</h3>
            <button type="button" onClick={() => setRoll((r) => r + 1)} className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              <Dices className="size-3.5" /> Another
            </button>
          </div>
          <div className={cn("grid gap-2", options + (none ? 1 : 0) > 3 ? "sm:grid-cols-4" : "sm:grid-cols-3")}>
            {sample.map((lines, o) => (
              <div key={o} className="rounded-xl border bg-background/60 p-3">
                <span className="mb-1.5 grid size-6 place-items-center rounded-md bg-primary text-xs font-bold text-primary-foreground">{LETTERS[o]}</span>
                <ul className="space-y-0.5 text-[0.8rem]">{lines.map((l) => <li key={l}>{l}</li>)}</ul>
              </div>
            ))}
            {none && <div className="grid place-items-center rounded-xl border border-dashed p-3 text-center text-[0.8rem] text-muted-foreground">None of these</div>}
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1">
              <span className="flex justify-between text-xs text-muted-foreground">Tasks per respondent <b className="num text-foreground">{tasks}</b></span>
              <input type="range" min={3} max={15} value={tasks} onChange={(e) => setTasks(Number(e.target.value))} aria-label="Tasks per respondent" />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Options per task</span>
              <select value={options} onChange={(e) => setOptions(Number(e.target.value))} className="h-8 rounded-lg border bg-card/60 px-2 text-sm">
                {[2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 self-end pb-1 text-sm">
              <input type="checkbox" checked={none} onChange={(e) => setNone(e.target.checked)} /> Allow “none”
            </label>
          </div>
          <p className="text-[0.7rem] text-muted-foreground">
            {profiles.toLocaleString()} possible versions; each respondent sees {tasks * options} of them in their own random, level-balanced tasks.
          </p>
        </div>
        <div className="space-y-3 rounded-2xl border bg-card p-4">
          <h3 className="text-sm font-semibold">Respondents</h3>
          <div>
            <div className="flex items-baseline justify-between text-xs text-muted-foreground">
              <span>Panel size · from {personaCount.toLocaleString()} personas</span>
              <span className="num text-sm font-semibold text-foreground">{panel}</span>
            </div>
            <input type="range" min={10} max={600} step={10} value={panel} onChange={(e) => setPanel(Number(e.target.value))} className="w-full" aria-label="Respondents" />
            <p className="text-[0.7rem] text-muted-foreground">{panel} model calls (one per respondent for all {tasks} tasks, cached on re-run) · {(panel * tasks).toLocaleString()} choices.</p>
          </div>
          <Chips label="Age" options={AGES} value={ages} onToggle={(v) => setAges((a) => toggle(a, v))} />
          <Chips label="Gender" options={GENDERS} value={genders} onToggle={(v) => setGenders((g) => toggle(g, v))} />
          <select className="h-9 w-full rounded-xl border bg-card/60 px-2.5 text-sm" value={model} onChange={(e) => setModel(e.target.value)} aria-label="Model">
            <option value="">App's vision model</option>
            {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
          </select>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Study name (optional)" maxLength={80} className="mr-auto h-10 max-w-xs" />
        {(problems[0] || run.error) && <p className="text-sm text-destructive">{run.error?.message ?? problems[0]}</p>}
        <Button size="lg" disabled={problems.length > 0 || run.isPending} onClick={() => run.mutate()}>
          {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Grid3x3 className="size-4" />}
          Field the study
        </Button>
      </div>
    </div>
  );
}

function Chips({ label, options, value, onToggle }: { label: string; options: string[]; value: string[]; onToggle: (v: string) => void }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="w-14 text-xs text-muted-foreground">{label}</span>
      {options.map((o) => (
        <button key={o} type="button" onClick={() => onToggle(o)}
          className={cn("rounded-full border px-2.5 py-0.5 text-xs", value.includes(o) ? "border-primary bg-primary text-primary-foreground" : "hover:border-foreground/25")}>
          {o}
        </button>
      ))}
      {value.length === 0 && <span className="text-[0.7rem] text-muted-foreground">all</span>}
    </div>
  );
}
