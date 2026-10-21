import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessagesSquare, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { draftPitchScript, marketingKeys, startPitch, type JobStatus } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";
import { queryKeys } from "@/shared/queries/keys";
import { formatMoney } from "@/shared/utils/money";

import type { Product } from "./products";

export function StaffPitchBuilder({ projectId, setupId, products, currency, personaCount, onStarted }: {
  projectId: string; setupId: string; products: Product[]; currency: string; personaCount: number; onStarted: (job: JobStatus) => void;
}) {
  const qc = useQueryClient();
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [sku, setSku] = useState(products[0]?.sku ?? "");
  const [name, setName] = useState("");
  const [aName, setAName] = useState("Current greeting");
  const [bName, setBName] = useState("Helpful recommendation");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [context, setContext] = useState("The shopper is browsing this product's shelf. An available employee offers help once; the shopper can decline.");
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
  const draft = useMutation({
    mutationFn: () => draftPitchScript(projectId, { setup_id: setupId, sku, context, product_facts: facts, current: a, direction }),
    onSuccess: (d) => { setB(d.script); setBName(d.name); },
  });
  return <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (ready) run.mutate(); }}>
    <section className="space-y-3 rounded-2xl border bg-card p-4">
      <h2 className="font-semibold">Staff script A/B test</h2>
      <p className="text-sm text-muted-foreground">Screen two greetings, recommendations or objection-handling scripts with the same synthetic shoppers. Each encounter is independent. Ratings help choose a field pilot; they do not predict sales.</p>
      <label className="block space-y-1 text-sm">Product held constant
        <select aria-label="Product held constant" value={sku} onChange={(e) => setSku(e.target.value)} className="block h-10 w-full rounded-xl border bg-card px-2">
          {products.map((p) => <option key={p.sku} value={p.sku}>{p.name} · {formatMoney(p.price, currency)} · {p.sku}</option>)}
        </select>
      </label>
      <label className="block space-y-1 text-sm">Encounter context
        <Textarea value={context} onChange={(e) => setContext(e.target.value)} maxLength={1200} required />
      </label>
      <label className="block space-y-1 text-sm">Verified product facts (optional)
        <Textarea value={facts} onChange={(e) => setFacts(e.target.value)} maxLength={1600} placeholder="Only facts you can verify, such as pack size, ingredients or usage. Keep the offer the same in both scripts." />
      </label>
      <p className="text-xs text-muted-foreground">Prices and promotions come from the selected layout. Avoid changing the offer between scripts if you want to isolate wording. Spoken tone, staff availability and queue time are outside this test.</p>
    </section>
    <div className="grid gap-3 md:grid-cols-2">
      {([{ arm: "A", label: aName, setLabel: setAName, value: a, setValue: setA }, { arm: "B", label: bName, setLabel: setBName, value: b, setValue: setB }]).map((v) =>
        <section key={v.arm} className="space-y-3 rounded-2xl border bg-card p-4">
          <h3 className="font-semibold">Script {v.arm}</h3>
          <Input aria-label={`Script ${v.arm} name`} value={v.label} onChange={(e) => v.setLabel(e.target.value)} maxLength={40} required />
          <Textarea aria-label={`Script ${v.arm} text`} value={v.value} onChange={(e) => v.setValue(e.target.value)} maxLength={1200} rows={6} required
            placeholder={v.arm === "A" ? "Write the exact words staff currently say." : "Write the alternative wording to test."} />
          <p className="text-xs text-muted-foreground">{v.value.length}/1,200 characters · name hidden from shoppers</p>
          {v.arm === "B" && (
            <div className="space-y-1.5 border-t pt-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <Input aria-label="Direction for script B" value={direction} onChange={(e) => setDirection(e.target.value.slice(0, 200))}
                  placeholder="Optional direction, e.g. lead with value, shorter, more personal" className="h-8 min-w-[12rem] flex-1 text-xs" />
                <Button type="button" size="sm" variant="outline" disabled={!sku || draft.isPending} onClick={() => draft.mutate()}>
                  {draft.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} Write an alternative
                </Button>
              </div>
              {draft.data?.differs_by && <p className="text-xs text-muted-foreground">{draft.data.differs_by} Same product and offer as script A.</p>}
              {draft.error && <p role="alert" className="text-xs text-destructive">{draft.error.message}</p>}
            </div>
          )}
        </section>)}
    </div>
    {(sameScripts || sameNames) && <p role="alert" className="text-sm text-destructive">Use distinct script names and different wording.</p>}
    <section className="grid gap-3 rounded-2xl border bg-card p-4 sm:grid-cols-2">
      <label className="space-y-1 text-sm">Requested shoppers
        <Input type="number" min={20} max={500} step={1} value={panel} onChange={(e) => setPanel(e.target.value)} required />
      </label>
      <label className="space-y-1 text-sm">Random seed
        <Input type="number" min={0} max={2_147_483_647} step={1} value={seed} onChange={(e) => setSeed(e.target.value)} required />
      </label>
      <label className="space-y-1 text-sm">Text model
        <select value={model} onChange={(e) => setModel(e.target.value)} className="block h-10 w-full rounded-xl border bg-card px-2">
          <option value="">App's text model</option>
          {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
        </select>
      </label>
      <label className="space-y-1 text-sm">Test name (optional)
        <Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
      </label>
      <p className="text-xs text-muted-foreground sm:col-span-2">{personaCount} saved personas. {validNumbers ? `${Math.min(count, personaCount)} shoppers × 2 scripts = ${2 * Math.min(count, personaCount)} planned model requests, plus retries if needed.` : "Choose 20–500 shoppers and a nonnegative integer seed."} Product, scripts and sampled personas are saved with the test.</p>
    </section>
    {personaCount < 20 && <p role="alert" className="text-sm text-destructive">Generate at least 20 personas before testing staff scripts.</p>}
    {run.error && <p role="alert" className="text-sm text-destructive">{run.error.message}</p>}
    <div className="flex justify-end"><Button type="submit" disabled={!ready || run.isPending}>
      {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <MessagesSquare className="size-4" />} Test staff scripts
    </Button></div>
  </form>;
}
