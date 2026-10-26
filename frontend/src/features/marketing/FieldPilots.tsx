import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus } from "lucide-react";

import { closePilot, createPilot, getPilot, listPilots, pilotCsvUrl, pilotKeys, type PilotView } from "@/shared/api/fieldPilot";
import type { PitchReport } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Textarea } from "@/shared/components/ui/textarea";
import { formatMoney, formatPercent, formatDecimal } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import { PilotPlanner, PilotPlanningSummary } from "./PilotPlanner";
import { emptyPlanningInputs, planningAssumptions } from "./pilotPlanning";
import { PilotImportHistory, PilotObservationReview } from "./PilotObservationReview";
import { PilotCollectionChecks } from "./PilotCollectionChecks";
import { PilotSensitivity } from "./PilotSensitivity";
import { PilotTiming } from "./PilotTiming";
import { PilotEconomics } from "./PilotEconomics";

type Translate = ReturnType<typeof useI18n>["t"];
const percent = (n: number | null, t: Translate) => n == null ? t("studioUnknown") : formatPercent(n, 1);
const points = (n: number | null, t: Translate) => n == null ? t("mkNotAvailable") : t("studioPp", { value: `${n > 0 ? "+" : ""}${formatDecimal(n * 100, 1)}` });

/** `onOpenScripts`: where pilots come from, offered while there is no script test to prepare one from. */
export function FieldPilots({ projectId, source, onOpenScripts }: { projectId: string; source?: PitchReport; onOpenScripts?: () => void }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState("");
  const [mode, setMode] = useState<"collection" | "results">("collection");
  const selectPilot = (id: string) => { setSelected(id); setMode("collection"); };
  const list = useQuery({ queryKey: pilotKeys.list(projectId), queryFn: ({ signal }) => listPilots(projectId, signal) });
  const view = useQuery({ queryKey: pilotKeys.detail(projectId, selected), queryFn: ({ signal }) => getPilot(projectId, selected, signal), enabled: !!selected && mode === "results" });
  const pilots = (list.data ?? []).filter((p) => !source || p.pitch_id === source.pitch_id);
  return <section className="space-y-4 rounded-2xl border bg-card p-4">
    <h2 className="text-lg font-semibold">{t("mkPilotsTitle")}</h2>
    <p className="text-sm text-muted-foreground">{t("mkPilotsIntro")}</p>
    {source ? <details><summary className="cursor-pointer text-sm font-medium">{t("mkPreparePilot")}</summary>
      <PilotBuilder projectId={projectId} source={source} onCreated={selectPilot} />
    </details> : <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <p className="min-w-0 flex-1 basis-80 text-sm text-muted-foreground">{t("mkPilotsHowTo")}</p>
      {onOpenScripts && <Button variant="outline" size="sm" onClick={onOpenScripts}>{t("mkOpenStaffScripts")}</Button>}
    </div>}
    {list.error && <p role="alert" className="text-sm text-destructive">{list.error.message}</p>}
    <div className="flex flex-wrap gap-2">{pilots.map((p) => <Button key={p.pilot_id} variant={selected === p.pilot_id ? "default" : "outline"} onClick={() => selectPilot(p.pilot_id)}>
      {p.name} · {p.enrolled}/{p.planned} · {p.finalized_at ? t("mkPilotClosed") : t("mkPilotCollecting")}
    </Button>)}</div>
    {list.isPending && <p className="text-sm">{t("mkLoadingPilots")}</p>}
    {!list.isPending && !list.error && pilots.length === 0 && <p className="text-sm text-muted-foreground">{t("mkNoPilots")}</p>}
    {selected && <div className="space-y-3">
      <div className="flex gap-2"><Button variant={mode === "collection" ? "default" : "outline"} onClick={() => setMode("collection")}>{t("mkCollectionChecks")}</Button><Button variant={mode === "results" ? "default" : "outline"} onClick={() => setMode("results")}>{t("mkObservationsResults")}</Button></div>
      {mode === "collection" ? <PilotCollectionChecks key={selected} projectId={projectId} pilotId={selected} /> : <>
        <Button variant="ghost" size="sm" onClick={() => void view.refetch()} disabled={view.isFetching}>{t("mkReloadPilot")}</Button>
        {view.error && <p role="alert" className="text-sm text-destructive">{view.error.message}</p>}
        {view.data ? <PilotResults key={`${selected}:${view.data.pilot.revision}`} projectId={projectId} view={view.data} /> : view.isPending && <p className="text-sm">{t("mkLoadingObservations")}</p>}
      </>}
    </div>}
  </section>;
}

export function PilotBuilder({ projectId, source, onCreated }: { projectId: string; source: PitchReport; onCreated: (id: string) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [name, setName] = useState(() => t("mkPilotDefaultName", { name: Array.from(source.name).slice(0, 65).join("") }));
  const [eligibility, setEligibility] = useState("");
  const [window, setWindow] = useState(() => t("mkPilotDefaultWindow"));
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
    <label className="block space-y-1 text-sm">{t("mkPilotName")}<Input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required /></label>
    <label className="block space-y-1 text-sm">{t("mkEligible")}<Textarea value={eligibility} onChange={(e) => setEligibility(e.target.value)} maxLength={600} required placeholder={t("mkEligiblePlaceholder")} /></label>
    <label className="block space-y-1 text-sm">{t("mkOutcomeWindow")}<Textarea value={window} onChange={(e) => setWindow(e.target.value)} maxLength={600} required /></label>
    <p className="text-sm">{t("mkTargetProduct", { name: source.product.name, sku: source.product.sku })}</p>
    <p className="text-xs text-muted-foreground">{t("mkAliasesHint")}</p>
    {blocks.map((b, i) => <div key={i} className="grid grid-cols-3 gap-2">
      <Input aria-label={t("mkStaffAlias", { n: i + 1 })} value={b.staff_id} maxLength={40} onChange={(e) => setBlocks(blocks.map((row, j) => j === i ? { ...row, staff_id: e.target.value } : row))} />
      <Input aria-label={t("mkShiftId", { n: i + 1 })} value={b.shift_id} maxLength={40} onChange={(e) => setBlocks(blocks.map((row, j) => j === i ? { ...row, shift_id: e.target.value } : row))} />
      <Input aria-label={t("mkPlannedEncounters", { n: i + 1 })} type="number" min={4} max={2000} step={2} value={b.encounters} onChange={(e) => setBlocks(blocks.map((row, j) => j === i ? { ...row, encounters: e.target.value } : row))} />
    </div>)}
    <div className="flex gap-2"><Button type="button" variant="outline" size="sm" disabled={blocks.length >= 30} onClick={() => setBlocks([...blocks, { staff_id: `staff_${blocks.length + 1}`, shift_id: "shift_1", encounters: "100" }])}><Plus className="size-4" /> {t("mkAddStaffShift")}</Button>
      {blocks.length > 1 && <Button type="button" variant="ghost" size="sm" onClick={() => setBlocks(blocks.slice(0, -1))}>{t("mkRemoveLastBlock")}</Button>}</div>
    <label className="block max-w-48 space-y-1 text-sm">{t("mkAllocationSeed")}<Input type="number" min={0} max={2_147_483_647} step={1} value={seed} onChange={(e) => setSeed(e.target.value)} required /></label>
    <PilotPlanner projectId={projectId} inputs={planningInputs} onChange={setPlanningInputs} counts={blocks.map((b) => Number(b.encounters))} onApply={(counts) => setBlocks(blocks.map((b, i) => ({ ...b, encounters: String(counts[i]) })))} />
    <p className="text-xs text-muted-foreground">{t("mkTargetEncounters", { count: Number.isFinite(total) ? total : "—" })}</p>
    {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
    <Button type="submit" disabled={!valid || create.isPending}>{t("mkSavePlan")}</Button>
  </form>;
}

export function PilotResults({ projectId, view }: { projectId: string; view: PilotView }) {
  const { t } = useI18n();
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
    <header className="space-y-2"><h3 className="font-semibold">{p.design.name} · {p.finalized_at ? t("mkClosedLocked") : t("mkPilotCollecting")}</h3>
      <p className="text-sm">{a.interpretation}</p>
      {a.inference_ready && <p className="text-lg font-semibold">{t("mkBMinusA", { value: points(a.difference, t) })} <span className="text-sm font-normal">{t("mkConservativeInterval", { low: points(a.ci_low, t), high: points(a.ci_high, t) })}</span></p>}
    </header>
    <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColAssignedArm")}</th><th>{t("mkColPlanned")}</th><th>{t("mkColEnrolled")}</th><th>{t("mkColKnownPurchases")}</th><th>{t("mkColMissingOutcomes")}</th><th>{t("mkColKnownRate")}</th><th>{t("mkColBounds")}</th></tr></thead>
      <tbody>{[a.a, a.b].map((arm) => <tr key={arm.arm} className="border-t"><th className="py-2 text-left">{arm.arm}</th><td>{arm.planned}</td><td>{arm.enrolled}</td><td>{arm.purchases} / {arm.observed}</td><td>{arm.missing_outcomes}</td><td>{percent(arm.observed_rate, t)}</td><td>{t("mkRangeTo", { low: percent(arm.missing_bound_low, t), high: percent(arm.missing_bound_high, t) })}</td></tr>)}</tbody>
    </table></div>
    <p className="text-xs text-muted-foreground">{t("mkSlotsSummary", { unrecorded: a.a.unrecorded + a.b.unrecorded, unused: a.a.unused + a.b.unused, notDelivered: a.a.not_delivered + a.b.not_delivered, unknownDelivery: a.a.delivery_unknown + a.b.delivery_unknown })}</p>
    <div className="flex flex-wrap items-center gap-3"><Button asChild variant="outline" size="sm"><a href={pilotCsvUrl(projectId, p.pilot_id)} download><Download className="size-4" /> {t("mkObservationCsv")}</a></Button>
    </div>
    {!p.finalized_at && <PilotObservationReview key={p.revision} projectId={projectId} pilot={p} disabled={close.isPending} onActive={setReviewActive} onSaved={saved} />}
    {!p.finalized_at && <div className="space-y-2 rounded-xl bg-muted/40 p-3 text-sm">
      <p>{t("mkEditHint")}</p>
      <p>{t("mkCloseHint")}</p>
      <label className="flex items-start gap-2"><input type="checkbox" checked={closing} onChange={(e) => setClosing(e.target.checked)} disabled={busy} />{t("mkEndingCollection")}</label>
      <Button variant="outline" disabled={!closing || !a.can_finalize || busy} onClick={() => close.mutate()}>{t("mkClosePilot")}</Button>
      {!a.can_finalize && <p className="text-xs text-muted-foreground">{t("mkBeforeClosing")}</p>}
    </div>}
    {close.error && <p role="alert" className="text-sm text-destructive">{close.error.message}</p>}
    <PilotImportHistory projectId={projectId} pilot={p} />
    <PilotSensitivity projectId={projectId} pilotId={p.pilot_id} revision={p.revision} eligible={!!p.finalized_at && a.inference_ready} />
    <PilotTiming key={`timing:${projectId}:${p.pilot_id}:${p.revision}`} projectId={projectId} pilotId={p.pilot_id} revision={p.revision} eligible={!!p.finalized_at && a.inference_ready} />
    <PilotEconomics key={`${p.pilot_id}:${p.revision}`} projectId={projectId} pilotId={p.pilot_id} revision={p.revision} currency={p.product.currency} eligible={!!p.finalized_at && a.inference_ready} />
    <details><summary className="cursor-pointer text-sm font-semibold">{t("mkSavedDesign")}</summary>
      <div className="mt-2 space-y-2 text-sm"><p>{p.product.name} · {p.product.sku} · {formatMoney(p.product.price, p.product.currency)} · {p.product.promo}</p>
        <p>{t("mkEligibility", { value: p.design.eligibility })}</p><p>{t("mkOutcomeWindowValue", { value: p.design.outcome_window })}</p><p>{t("mkContextValue", { value: p.context })}</p><p>{t("mkFactsValue", { value: p.product_facts || t("mkNoneSupplied") })}</p>
        {p.variants.map((v, i) => <p key={i} className="whitespace-pre-wrap"><b>{i === 0 ? "A" : "B"} · {v.name}:</b> {v.script}</p>)}
        <p>{t("mkSeedRevisionSource", { seed: String(p.design.seed), revision: String(p.revision), source: p.pitch_id })}</p>
      </div>
    </details>
    <details><summary className="cursor-pointer text-sm font-semibold">{t("mkStaffShiftChecks")}</summary>
      <div className="mt-2 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColStaffShift")}</th><th>{t("mkColAEnrolled")}</th><th>{t("mkColBEnrolled")}</th><th>{t("mkColKnownDiff")}</th></tr></thead>
        <tbody>{a.blocks.map((b) => <tr key={`${b.staff_id}:${b.shift_id}`}><td className="py-1">{b.staff_id} / {b.shift_id}</td><td>{b.a.enrolled}/{b.a.planned}</td><td>{b.b.enrolled}/{b.b.planned}</td><td>{points(b.observed_diff, t)}</td></tr>)}</tbody>
      </table></div>
    </details>
    {p.planning && <details><summary className="cursor-pointer text-sm font-semibold">{t("mkSavedPlanning")}</summary><div className="mt-2"><PilotPlanningSummary plan={p.planning} /></div></details>}
    <details><summary className="cursor-pointer text-sm font-semibold">{t("studioMethodLimitations")}</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{a.notes.map((n) => <li key={n}>{n}</li>)}</ul></details>
  </div>;
}
