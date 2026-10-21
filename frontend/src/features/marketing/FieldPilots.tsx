import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus } from "lucide-react";

import { closePilot, createPilot, getPilot, listPilots, pilotCsvUrl, pilotKeys, type PilotView } from "@/shared/api/fieldPilot";
import type { PitchReport } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";
import { formatMoney } from "@/shared/utils/money";
import { PilotPlanner, PilotPlanningSummary } from "./PilotPlanner";
import { emptyPlanningInputs, planningAssumptions } from "./pilotPlanning";
import { PilotImportHistory, PilotObservationReview } from "./PilotObservationReview";
import { PilotCollectionChecks } from "./PilotCollectionChecks";
import { PilotSensitivity } from "./PilotSensitivity";

const percent = (n: number | null) => n == null ? "Unknown" : `${(n * 100).toFixed(1)}%`;
const points = (n: number | null) => n == null ? "Not available" : `${n > 0 ? "+" : ""}${(n * 100).toFixed(1)} pp`;

export function FieldPilots({ projectId, source }: { projectId: string; source?: PitchReport }) {
  const [selected, setSelected] = useState("");
  const [mode, setMode] = useState<"collection" | "results">("collection");
  const selectPilot = (id: string) => { setSelected(id); setMode("collection"); };
  const list = useQuery({ queryKey: pilotKeys.list(projectId), queryFn: ({ signal }) => listPilots(projectId, signal) });
  const view = useQuery({ queryKey: pilotKeys.detail(projectId, selected), queryFn: ({ signal }) => getPilot(projectId, selected, signal), enabled: !!selected && mode === "results" });
  const pilots = (list.data ?? []).filter((p) => !source || p.pitch_id === source.pitch_id);
  return <section className="space-y-4 rounded-2xl border bg-card p-4">
    <h2 className="text-lg font-semibold">Observed field pilots</h2>
    <p className="text-sm text-muted-foreground">Run the scripts with real eligible encounters, balanced within each staff/shift. Keep assigned groups even when a customer declines the script. No model calls are made here.</p>
    {source ? <details><summary className="cursor-pointer text-sm font-medium">Prepare a field pilot from these scripts</summary>
      <PilotBuilder projectId={projectId} source={source} onCreated={selectPilot} />
    </details> : <p className="text-sm text-muted-foreground">To prepare a pilot, open a completed test under Staff scripts and choose “Prepare a field pilot from these scripts”. Saved pilots remain accessible here.</p>}
    {list.error && <p role="alert" className="text-sm text-destructive">{list.error.message}</p>}
    <div className="flex flex-wrap gap-2">{pilots.map((p) => <Button key={p.pilot_id} variant={selected === p.pilot_id ? "default" : "outline"} onClick={() => selectPilot(p.pilot_id)}>
      {p.name} · {p.enrolled}/{p.planned} · {p.finalized_at ? "Closed" : "Collecting"}
    </Button>)}</div>
    {list.isPending && <p className="text-sm">Loading pilots…</p>}
    {!list.isPending && !list.error && pilots.length === 0 && <p className="text-sm text-muted-foreground">No field pilots yet.</p>}
    {selected && <div className="space-y-3">
      <div className="flex gap-2"><Button variant={mode === "collection" ? "default" : "outline"} onClick={() => setMode("collection")}>Collection checks</Button><Button variant={mode === "results" ? "default" : "outline"} onClick={() => setMode("results")}>Observations and results</Button></div>
      {mode === "collection" ? <PilotCollectionChecks key={selected} projectId={projectId} pilotId={selected} /> : <>
        <Button variant="ghost" size="sm" onClick={() => void view.refetch()} disabled={view.isFetching}>Reload pilot</Button>
        {view.error && <p role="alert" className="text-sm text-destructive">{view.error.message}</p>}
        {view.data ? <PilotResults key={`${selected}:${view.data.pilot.revision}`} projectId={projectId} view={view.data} /> : view.isPending && <p className="text-sm">Loading observations…</p>}
      </>}
    </div>}
  </section>;
}

export function PilotBuilder({ projectId, source, onCreated }: { projectId: string; source: PitchReport; onCreated: (id: string) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState(`${source.name.slice(0, 65)} field pilot`);
  const [eligibility, setEligibility] = useState("");
  const [window, setWindow] = useState("Purchase of the target SKU before this store visit ends.");
  const [seed, setSeed] = useState("1");
  const [blocks, setBlocks] = useState([{ staff_id: "staff_1", shift_id: "shift_1", encounters: "100" }]);
  const [planningInputs, setPlanningInputs] = useState(emptyPlanningInputs);
  const planning = planningAssumptions(planningInputs);
  const total = blocks.reduce((n, b) => n + Number(b.encounters), 0);
  const aliases = /^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/;
  const valid = name.trim() && eligibility.trim() && window.trim() && seed.trim() && Number.isInteger(Number(seed)) && Number(seed) >= 0 && Number(seed) <= 2_147_483_647
    && (!planningInputs.enabled || !!planning)
    && total >= 40 && total <= 10000 && new Set(blocks.map((b) => `${b.staff_id}:${b.shift_id}`)).size === blocks.length
    && blocks.every((b) => aliases.test(b.staff_id) && aliases.test(b.shift_id) && Number.isInteger(Number(b.encounters)) && Number(b.encounters) >= 4 && Number(b.encounters) <= 2000 && Number(b.encounters) % 2 === 0);
  const create = useMutation({
    mutationFn: () => createPilot(projectId, source.pitch_id, { name: name.trim(), eligibility: eligibility.trim(), outcome_window: window.trim(), seed: Number(seed), blocks: blocks.map((b) => ({ ...b, encounters: Number(b.encounters) })), planning }),
    onSuccess: async (result) => {
      qc.setQueryData(pilotKeys.detail(projectId, result.pilot.pilot_id), result);
      await qc.invalidateQueries({ queryKey: pilotKeys.list(projectId) });
      onCreated(result.pilot.pilot_id);
    },
  });
  return <form className="mt-4 space-y-3" onSubmit={(e) => { e.preventDefault(); if (valid && !create.isPending) create.mutate(); }}>
    <label className="block space-y-1 text-sm">Pilot name<Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required /></label>
    <label className="block space-y-1 text-sm">Eligible encounters<Textarea value={eligibility} onChange={(e) => setEligibility(e.target.value)} maxLength={600} required placeholder="Define who qualifies before seeing their assigned script. Use each customer once; do not enter customer identities." /></label>
    <label className="block space-y-1 text-sm">Purchase outcome window<Textarea value={window} onChange={(e) => setWindow(e.target.value)} maxLength={600} required /></label>
    <p className="text-sm">Target product: {source.product.name} · {source.product.sku}. The script, offer and product snapshot will be fixed.</p>
    <p className="text-xs text-muted-foreground">Use anonymous staff aliases and unique shift IDs (for example staff_1 / 2026-10-21-am). Each block needs an even 4–2,000 encounters; total 40–10,000. Each block allocates half to A and half to B.</p>
    {blocks.map((b, i) => <div key={i} className="grid grid-cols-3 gap-2">
      <Input aria-label={`Staff alias ${i + 1}`} value={b.staff_id} maxLength={40} onChange={(e) => setBlocks(blocks.map((row, j) => j === i ? { ...row, staff_id: e.target.value } : row))} />
      <Input aria-label={`Shift ID ${i + 1}`} value={b.shift_id} maxLength={40} onChange={(e) => setBlocks(blocks.map((row, j) => j === i ? { ...row, shift_id: e.target.value } : row))} />
      <Input aria-label={`Planned encounters ${i + 1}`} type="number" min={4} max={2000} step={2} value={b.encounters} onChange={(e) => setBlocks(blocks.map((row, j) => j === i ? { ...row, encounters: e.target.value } : row))} />
    </div>)}
    <div className="flex gap-2"><Button type="button" variant="outline" size="sm" disabled={blocks.length >= 30} onClick={() => setBlocks([...blocks, { staff_id: `staff_${blocks.length + 1}`, shift_id: "shift_1", encounters: "100" }])}><Plus className="size-4" /> Add staff/shift</Button>
      {blocks.length > 1 && <Button type="button" variant="ghost" size="sm" onClick={() => setBlocks(blocks.slice(0, -1))}>Remove last block</Button>}</div>
    <label className="block max-w-48 space-y-1 text-sm">Allocation seed<Input type="number" min={0} max={2_147_483_647} step={1} value={seed} onChange={(e) => setSeed(e.target.value)} required /></label>
    <PilotPlanner projectId={projectId} inputs={planningInputs} onChange={setPlanningInputs} counts={blocks.map((b) => Number(b.encounters))} onApply={(counts) => setBlocks(blocks.map((b, i) => ({ ...b, encounters: String(counts[i]) })))} />
    <p className="text-xs text-muted-foreground">Target: {Number.isFinite(total) ? total : "—"} encounters. Choose sample size before collecting data. The saved plan cannot be edited. Use assignments in sequence without inspecting future arms or selecting customers by arm.</p>
    {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
    <Button type="submit" disabled={!valid || create.isPending}>Save fixed pilot plan</Button>
  </form>;
}

export function PilotResults({ projectId, view }: { projectId: string; view: PilotView }) {
  const { pilot: p, analysis: a } = view;
  const qc = useQueryClient();
  const [closing, setClosing] = useState(false);
  const [reviewActive, setReviewActive] = useState(false);
  const saved = async (result: PilotView) => {
    await qc.cancelQueries({ queryKey: pilotKeys.detail(projectId, p.pilot_id) });
    qc.setQueryData(pilotKeys.detail(projectId, p.pilot_id), result);
    await qc.invalidateQueries({ queryKey: pilotKeys.list(projectId), exact: true });
    await qc.invalidateQueries({ queryKey: pilotKeys.collection(projectId, p.pilot_id), exact: true });
  };
  const close = useMutation({ mutationFn: () => closePilot(projectId, p.pilot_id, p.revision), onSuccess: saved });
  const busy = reviewActive || close.isPending;
  return <div className="space-y-4">
    <header className="space-y-2"><h3 className="font-semibold">{p.design.name} · {p.finalized_at ? "Closed and locked" : "Collecting"}</h3>
      <p className="text-sm">{a.interpretation}</p>
      {a.inference_ready && <p className="text-lg font-semibold">B − A: {points(a.difference)} <span className="text-sm font-normal">· conservative 95% interval {points(a.ci_low)} to {points(a.ci_high)}</span></p>}
    </header>
    <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Assigned arm</th><th>Planned</th><th>Enrolled</th><th>Known purchases</th><th>Missing outcomes</th><th>Known-outcome rate</th><th>Missing-outcome bounds</th></tr></thead>
      <tbody>{[a.a, a.b].map((arm) => <tr key={arm.arm} className="border-t"><th className="py-2 text-left">{arm.arm}</th><td>{arm.planned}</td><td>{arm.enrolled}</td><td>{arm.purchases} / {arm.observed}</td><td>{arm.missing_outcomes}</td><td>{percent(arm.observed_rate)}</td><td>{percent(arm.missing_bound_low)} to {percent(arm.missing_bound_high)}</td></tr>)}</tbody>
    </table></div>
    <p className="text-xs text-muted-foreground">Unrecorded slots: {a.a.unrecorded + a.b.unrecorded} · unused slots: {a.a.unused + a.b.unused} · enrolled encounters without script delivery: {a.a.not_delivered + a.b.not_delivered} · unknown delivery: {a.a.delivery_unknown + a.b.delivery_unknown}. Missing-outcome bounds are not confidence intervals.</p>
    <div className="flex flex-wrap items-center gap-3"><Button asChild variant="outline" size="sm"><a href={pilotCsvUrl(projectId, p.pilot_id)} download><Download className="size-4" /> Observation sheet CSV</a></Button>
    </div>
    {!p.finalized_at && <PilotObservationReview key={p.revision} projectId={projectId} pilot={p} disabled={close.isPending} onActive={setReviewActive} onSaved={saved} />}
    {!p.finalized_at && <div className="space-y-2 rounded-xl bg-muted/40 p-3 text-sm">
      <p>Edit only enrolled, delivered and purchased: 1 = yes, 0 = no, blank = unknown. Mark enrolled=0 only for an unused slot; keep its other outcomes blank. Record refused scripts as delivered=0 for an enrolled encounter, and still record its purchase outcome.</p>
      <p>The full CSV replaces previously uploaded observations after review. Keep every row and all assignment columns. Discard or apply a pending preview before closing. Close only after the saved outcome window has elapsed. Closing below target leaves a descriptive report.</p>
      <label className="flex items-start gap-2"><input type="checkbox" checked={closing} onChange={(e) => setClosing(e.target.checked)} disabled={busy} />I am ending collection and locking these observations.</label>
      <Button variant="outline" disabled={!closing || !a.can_finalize || busy} onClick={() => close.mutate()}>Close and lock pilot</Button>
      {!a.can_finalize && <p className="text-xs text-muted-foreground">Before closing, record every slot and all enrolled purchase and delivery outcomes.</p>}
    </div>}
    {close.error && <p role="alert" className="text-sm text-destructive">{close.error.message}</p>}
    <PilotImportHistory projectId={projectId} pilot={p} />
    <PilotSensitivity projectId={projectId} pilotId={p.pilot_id} revision={p.revision} eligible={!!p.finalized_at && a.inference_ready} />
    <details><summary className="cursor-pointer text-sm font-semibold">Saved design and scripts</summary>
      <div className="mt-2 space-y-2 text-sm"><p>{p.product.name} · {p.product.sku} · {formatMoney(p.product.price, p.product.currency)} · {p.product.promo}</p>
        <p>Eligibility: {p.design.eligibility}</p><p>Outcome window: {p.design.outcome_window}</p><p>Context: {p.context}</p><p>Product facts: {p.product_facts || "None supplied"}</p>
        {p.variants.map((v, i) => <p key={i} className="whitespace-pre-wrap"><b>{i === 0 ? "A" : "B"} · {v.name}:</b> {v.script}</p>)}
        <p>Seed {p.design.seed} · revision {p.revision} · source {p.pitch_id}</p>
      </div>
    </details>
    <details><summary className="cursor-pointer text-sm font-semibold">Staff/shift checks</summary>
      <div className="mt-2 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Staff / shift</th><th>A enrolled / planned</th><th>B enrolled / planned</th><th>Known-outcome difference</th></tr></thead>
        <tbody>{a.blocks.map((b) => <tr key={`${b.staff_id}:${b.shift_id}`}><td className="py-1">{b.staff_id} / {b.shift_id}</td><td>{b.a.enrolled}/{b.a.planned}</td><td>{b.b.enrolled}/{b.b.planned}</td><td>{points(b.observed_diff)}</td></tr>)}</tbody>
      </table></div>
    </details>
    {p.planning && <details><summary className="cursor-pointer text-sm font-semibold">Saved sample planning assessment</summary><div className="mt-2"><PilotPlanningSummary plan={p.planning} /></div></details>}
    <details><summary className="cursor-pointer text-sm font-semibold">Method and limitations</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{a.notes.map((n) => <li key={n}>{n}</li>)}</ul></details>
  </div>;
}
