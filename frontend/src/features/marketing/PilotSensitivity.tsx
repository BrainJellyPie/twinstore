import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { sensitivityCsvUrl, type SensitivityScope } from "@/shared/api/fieldSensitivity";
import { pilotSensitivityQuery } from "@/services/queries/fieldSensitivity";
import { Button } from "@/shared/components/ui/button";

const points = (value: number | null) => value == null ? "Not estimable" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)} pp`;
const scopes: { key: SensitivityScope; label: string }[] = [
  { key: "staff", label: "Leave one staff alias out" },
  { key: "shift", label: "Leave one shift ID out" },
  { key: "block", label: "Leave one staff/shift block out" },
];

export function PilotSensitivity({ projectId, pilotId, revision, eligible }: { projectId: string; pilotId: string; revision: number; eligible: boolean }) {
  const [requested, setRequested] = useState(false);
  const query = useQuery(pilotSensitivityQuery(projectId, pilotId, revision, eligible && requested));
  const report = !query.error && requested && eligible ? query.data : undefined;
  return <section aria-label="Staff and shift sensitivity" className="space-y-3 rounded-xl border p-3">
    <h4 className="font-semibold">Staff and shift sensitivity</h4>
    <p className="text-sm text-muted-foreground">Check how the B − A conversion difference changes when one staff alias, shift ID or staff/shift block is removed. These are descriptive checks, not new significance tests or staff performance ratings. Keep the full-plan result as primary.</p>
    {!eligible ? <p className="text-sm">Available only after closing a fully completed fixed plan with every planned encounter and outcome recorded. Do not close early to unlock this report.</p> : <>
      <Button variant="outline" size="sm" disabled={query.isFetching} onClick={() => { if (requested) void query.refetch(); else setRequested(true); }}>{requested ? "Reload sensitivity checks" : "Show sensitivity checks"}</Button>
      {query.isFetching && <p className="text-sm">Loading sensitivity checks…</p>}
      {query.error && <p role="alert" className="text-sm text-destructive">{query.error.message}</p>}
    </>}
    {report && <div className="space-y-3">
      <p className="text-sm">Full-plan B − A: <b>{points(report.difference)}</b> · {report.planned_encounters} encounters · {report.blocks} blocks · target SKU {report.target_sku}</p>
      <p className="text-xs text-muted-foreground">Locked revision {report.revision} · {report.finalized_at}. An opposite sign excludes exact zeros. The ranges below describe deletion estimates; they are not confidence intervals.</p>
      {scopes.map(({ key, label }) => {
        const summary = report.summaries.find((s) => s.scope === key);
        return <details key={key} className="rounded-lg border p-3">
          <summary className="cursor-pointer text-sm font-medium">{label}{summary && ` · ${summary.opposite_sign_count} of ${summary.estimable} estimable deletions have an opposite sign`}</summary>
          {summary && <p className="my-2 text-xs">Estimate range: {points(summary.minimum)} to {points(summary.maximum)} · largest absolute change: {points(summary.max_absolute_change)} · comparisons unavailable after deletion: {summary.groups - summary.estimable}.</p>}
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Excluded group</th><th>Removed encounters / weight</th><th>Remaining encounters</th><th>B − A after removal</th><th>Change from full plan</th><th>Opposite sign</th></tr></thead>
            <tbody>{report.groups.filter((group) => group.scope === key).map((group) => <tr key={`${group.staff_id}:${group.shift_id}`} className="border-t"><th className="py-2 text-left">{[group.staff_id, group.shift_id].filter(Boolean).join(" / ")}</th><td>{group.removed_encounters} / {(group.removed_weight * 100).toFixed(1)}%</td><td>{group.remaining_encounters}</td><td>{points(group.difference)}</td><td>{points(group.change)}</td><td>{group.opposite_sign == null ? "Not estimable" : group.opposite_sign ? "Yes" : "No"}</td></tr>)}</tbody>
          </table></div>
        </details>;
      })}
      <Button asChild variant="outline" size="sm"><a href={sensitivityCsvUrl(projectId, report.pilot_id, report.revision)} download>Export all sensitivity checks CSV</a></Button>
      <p className="text-xs text-muted-foreground">Export includes every group in all three scopes at this revision. Differences and changes in the CSV are proportions, not percentage points. Repeated plan totals must not be summed. An unavailable estimate is blank, not zero.</p>
      <details><summary className="cursor-pointer text-sm font-medium">Sensitivity method and limitations</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
