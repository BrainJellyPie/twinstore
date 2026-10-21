import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { pilotEconomicsExport, pilotEconomicsPreview } from "@/services/mutations/fieldEconomics";
import type { PilotEconomicsRequest } from "@/shared/api/fieldEconomics";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { currencyCode } from "@/shared/utils/money";

type Assumption = Exclude<keyof PilotEconomicsRequest, "revision" | "currency">;
const fields: { key: Assumption; label: string; max: number }[] = [
  { key: "contribution_per_conversion_minor", label: "Contribution per converted encounter (minor units)", max: 1_000_000_000 },
  { key: "labor_per_hour_minor", label: "Loaded labor cost per hour (minor units)", max: 1_000_000_000 },
  { key: "seconds_per_encounter_a", label: "Average staff seconds per assigned encounter · A", max: 3600 },
  { key: "seconds_per_encounter_b", label: "Average staff seconds per assigned encounter · B", max: 3600 },
  { key: "eligible_encounters_per_day", label: "Assumed eligible encounters per day", max: 1_000_000 },
];
const number = (value: number) => value.toLocaleString(undefined, { maximumSignificantDigits: 8 });
const points = (value: number) => `${number(value * 100)} pp`;

export function PilotEconomics({ projectId, pilotId, revision, currency, eligible }: {
  projectId: string; pilotId: string; revision: number; currency: string; eligible: boolean;
}) {
  const [draft, setDraft] = useState<Record<Assumption, string>>({ contribution_per_conversion_minor: "", labor_per_hour_minor: "",
    seconds_per_encounter_a: "", seconds_per_encounter_b: "", eligible_encounters_per_day: "" });
  const preview = useMutation(pilotEconomicsPreview(projectId, pilotId));
  const download = useMutation({ ...pilotEconomicsExport(projectId, pilotId), onSuccess: (blob) => {
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `${pilotId}-cost-scenario-r${revision}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  } });
  const busy = preview.isPending || download.isPending;
  const valid = fields.every(({ key, max }) => /^\d+$/.test(draft[key]) && Number.isSafeInteger(Number(draft[key])) && Number(draft[key]) <= max);
  const request = (): PilotEconomicsRequest => ({ revision, currency,
    contribution_per_conversion_minor: Number(draft.contribution_per_conversion_minor), labor_per_hour_minor: Number(draft.labor_per_hour_minor),
    seconds_per_encounter_a: Number(draft.seconds_per_encounter_a), seconds_per_encounter_b: Number(draft.seconds_per_encounter_b),
    eligible_encounters_per_day: Number(draft.eligible_encounters_per_day) });
  const report = eligible ? preview.data : undefined;
  return <section aria-label="Staff-script cost scenario" className="space-y-3 rounded-xl border p-3">
    <h4 className="font-semibold">Staff-script cost scenario</h4>
    <p className="text-sm text-muted-foreground">Would the observed conversion difference cover extra staff time under your cost assumptions? This is a conditional scenario for switching A to B, not realized profit or a forecast of daily sales.</p>
    {!eligible ? <p className="text-sm">Available after closing a fully completed fixed plan. Do not close early or omit records to calculate costs.</p> : <>
      <p className="text-xs">Use {currencyCode(currency)} minor units (for example, USD cents or KRW won). Enter the same net target-product contribution per buyer for both arms after product costs, discounts and returns, before the staff time below. Do not substitute selling price or per-unit margin without verifying units per buyer.</p>
      <p className="text-xs">Time means whole average staff seconds per assigned eligible encounter, including refusals and non-delivery. Enter all assumptions explicitly; blank means unknown, not zero. Labor cost is not inferred from the saved product price.</p>
      <div className="grid gap-3 sm:grid-cols-2">{fields.map(({ key, label, max }) => <label key={key} className="space-y-1 text-xs">{label}<Input type="number" min={0} max={max} step={1} value={draft[key]} disabled={busy} onChange={(e) => {
        preview.reset(); download.reset(); setDraft({ ...draft, [key]: e.target.value });
      }} /></label>)}</div>
      <Button size="sm" variant="outline" disabled={!valid || busy} onClick={() => preview.mutate(request())}>Calculate cost scenario</Button>
      {!valid && <p className="text-xs text-muted-foreground">Enter whole nonnegative values within the displayed input limits. Enter 0 explicitly when that is your assumption.</p>}
      {preview.isPending && <p className="text-sm">Calculating with the locked pilot and explicit cost assumptions…</p>}
      {(preview.error || download.error) && <p role="alert" className="text-sm text-destructive">{preview.error?.message || download.error?.message}</p>}
    </>}
    {report && <div className="space-y-3 text-sm">
      <p>Locked revision {report.assumptions.revision} · {report.planned_encounters} encounters · target SKU {report.target_sku}</p>
      <p>Full-plan conversion difference: {points(report.conversion_difference)} · original conservative 95% interval {points(report.conversion_ci_low)} to {points(report.conversion_ci_high)}.</p>
      <p>Incremental labor per encounter: {number(report.incremental_labor_minor)} minor units. Break-even conversion difference: <b>{report.break_even_difference == null ? "Undefined at zero contribution" : points(report.break_even_difference)}</b>.</p>
      {report.break_even_difference != null && Math.abs(report.break_even_difference) > 1 && <p className="text-xs">The break-even threshold is outside the possible −100 to +100 pp conversion-difference range. It is shown without clipping.</p>}
      <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="text-left">Conditional incremental contribution ({currencyCode(report.assumptions.currency)} minor units)</caption><thead><tr className="text-left"><th>Scenario</th><th>Estimate</th><th>Conditional low</th><th>Conditional high</th></tr></thead><tbody>{[
        { label: "Per assigned encounter", value: report.per_encounter }, { label: `Daily scenario (${report.assumptions.eligible_encounters_per_day} encounters)`, value: report.per_day },
      ].map(({ label, value }) => <tr key={label} className="border-t"><th className="py-2 text-left">{label}</th><td>{number(value.estimate_minor)}</td><td>{number(value.low_minor)}</td><td>{number(value.high_minor)}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground">These ranges transform the original conversion interval with costs and traffic held fixed. They exclude uncertainty in those inputs and are not prediction intervals for realized daily profit. Trying different costs creates scenarios, not new evidence. Other basket effects and fixed implementation costs are excluded.</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => { if (preview.variables) download.mutate(preview.variables); }}>Export cost scenario CSV</Button>
      <details><summary className="cursor-pointer text-sm">Cost scenario method and limitations</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
