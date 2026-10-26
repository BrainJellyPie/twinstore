import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getPilotCollection, pilotFollowupCsvUrl, pilotKeys, type CollectionCounts, type PilotCollectionReport } from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";

const rate = (value: number | null, unknown: string) => value == null ? unknown : `${(value * 100).toFixed(1)}%`;

export function PilotCollectionChecks({ projectId, pilotId }: { projectId: string; pilotId: string }) {
  const { t } = useI18n();
  const query = useQuery({ queryKey: pilotKeys.collection(projectId, pilotId), queryFn: ({ signal }) => getPilotCollection(projectId, pilotId, signal) });
  return <section className="space-y-3">
    <Button variant="ghost" size="sm" onClick={() => void query.refetch()} disabled={query.isFetching}>{t("mkReloadChecks")}</Button>
    {query.error && <p role="alert" className="text-sm text-destructive">{query.error.message}</p>}
    {query.isFetching && <p className="text-sm text-muted-foreground">{t("mkLoadingChecks")}</p>}
    {query.data && <CollectionReport key={`${query.data.pilot_id}:${query.data.revision}`} projectId={projectId} report={query.data} />}
  </section>;
}

function CollectionReport({ projectId, report: r }: { projectId: string; report: PilotCollectionReport }) {
  const { t } = useI18n();
  const [block, setBlock] = useState("all");
  const [issue, setIssue] = useState("all");
  const [page, setPage] = useState(0);
  const tasks = r.tasks.filter((t) => (block === "all" || `${t.staff_id}:${t.shift_id}` === block) && (issue === "all" || t.issues.some((i) => i === issue)));
  const blocks = r.blocks.filter((b) => block === "all" || `${b.staff_id}:${b.shift_id}` === block);
  return <div className="space-y-4">
    <header className="space-y-1"><h3 className="font-semibold">{t("mkChecksTitle", { name: r.name })}</h3>
      <p className="text-xs text-muted-foreground">{t("mkSavedRevision", { revision: String(r.revision), at: r.updated_at })}</p>
      <p className="text-sm">{r.finalized_at ? t("mkChecksClosed") : t("mkChecksOpen")}</p>
      <p className="text-sm">{t("mkOutcomeWindowValue", { value: r.outcome_window })}</p>
    </header>
    <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
      <p className="rounded-xl bg-muted/40 p-3">{t("mkCompleteEnrolled")} <b>{r.counts.complete_enrolled} / {r.counts.enrolled}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">{t("mkUnknownPurchase")} <b>{r.counts.missing_purchase}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">{t("mkUnknownDelivery")} <b>{r.counts.missing_delivery}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">{t("mkEnrollmentGaps")} <b>{r.recording_gaps}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">{t("mkTailSlots")} <b>{r.unrecorded_tail}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">{t("mkUnusedBefore")} <b>{r.unused_before_enrolled}</b></p>
    </div>
    <p className="text-sm">{t("mkCountsLine", { enrolled: r.counts.enrolled, unused: r.counts.unused, planned: r.counts.planned })} {r.can_finalize ? r.target_completed ? t("mkAllComplete") : t("mkBelowTarget") : t("mkNeedsRecording")}</p>
    <p className="text-xs text-muted-foreground">{t("mkTailHint")}</p>
    <label className="block text-sm">{t("mkStaffShiftFilter")}<select className="ml-2 rounded-md border bg-background p-2" value={block} onChange={(e) => { setBlock(e.target.value); setPage(0); }}>
      <option value="all">{t("mkAllStaffShifts")}</option>{r.blocks.map((b) => <option key={`${b.staff_id}:${b.shift_id}`} value={`${b.staff_id}:${b.shift_id}`}>{b.staff_id} / {b.shift_id}</option>)}
    </select></label>
    <div className="space-y-2">{blocks.map((b) => <details className="rounded-xl border p-3" key={`${b.staff_id}:${b.shift_id}`}>
      <summary className="cursor-pointer text-sm font-medium">{t("mkBlockSummary", { block: `${b.staff_id} / ${b.shift_id}`, complete: b.counts.complete_enrolled, enrolled: b.counts.enrolled, unknown: b.counts.missing_purchase })}</summary>
      <p className="my-2 text-xs">{t("mkBlockDetail", { last: b.last_recorded_sequence == null ? t("studioNone") : String(b.last_recorded_sequence), gaps: b.recording_gaps, tail: b.unrecorded_tail, unused: b.unused_before_enrolled })}</p>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColArmShort")}</th><th>{t("mkColEnrolledPlanned")}</th><th>{t("mkColCompleteEnrolled")}</th><th>{t("mkColPurchaseUnknown")}</th><th>{t("mkColDeliveryUnknown")}</th><th>{t("mkColNonDelivery")}</th></tr></thead>
        <tbody><CountsRow label="A" counts={b.a} /><CountsRow label="B" counts={b.b} /></tbody>
      </table></div>
      <p className="mt-2 text-xs text-muted-foreground">{t("mkMissingnessGap", { value: b.purchase_missing_gap == null ? t("studioUnknown") : t("studioPp", { value: (b.purchase_missing_gap * 100).toFixed(1) }) })}</p>
    </details>)}</div>
    <section className="space-y-3">
      <h4 className="font-semibold">{t("mkFollowUp")}</h4>
      <p className="text-sm">{t("mkFollowUpIntro", { count: r.tasks.length })}</p>
      <div className="flex flex-wrap items-center gap-3"><label className="text-sm">{t("mkCheckType")}<select className="ml-2 rounded-md border bg-background p-2" value={issue} onChange={(e) => { setIssue(e.target.value); setPage(0); }}>
        <option value="all">{t("mkAllChecks")}</option>{r.guidance.map((g) => <option key={g.issue} value={g.issue}>{g.title}</option>)}
      </select></label><Button asChild variant="outline" size="sm"><a href={pilotFollowupCsvUrl(projectId, r.pilot_id)} download>{t("mkDownloadFollowUp")}</a></Button></div>
      <p className="text-xs text-muted-foreground">{t("mkFollowUpDownloadHint")}</p>
      {tasks.length ? <><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColStaffShift")}</th><th>{t("mkColSequenceArm")}</th><th>{t("mkColCheckAction")}</th></tr></thead>
        <tbody>{tasks.slice(page * 50, (page + 1) * 50).map((task) => <tr className="border-t align-top" key={task.assignment_id}><td className="py-2">{task.staff_id} / {task.shift_id}</td><td className="py-2">{task.sequence} / {task.arm}</td><td className="space-y-2 py-2">{task.issues.map((code) => {
          const guidance = r.guidance.find((g) => g.issue === code);
          return <p key={code}><b>{guidance?.title ?? code}:</b> {guidance?.action}</p>;
        })}</td></tr>)}</tbody></table></div>
        <div className="flex items-center gap-2 text-xs"><Button type="button" size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>{t("mkPrevChecks")}</Button><span>{t("mkAssignmentsRange", { from: page * 50 + 1, to: Math.min((page + 1) * 50, tasks.length), total: tasks.length })}</span><Button type="button" size="sm" variant="ghost" disabled={(page + 1) * 50 >= tasks.length} onClick={() => setPage(page + 1)}>{t("mkNextChecks")}</Button></div>
      </> : <p className="text-sm">{t("mkNoChecksMatch")}</p>}
    </section>
    <details><summary className="cursor-pointer text-sm font-semibold">{t("mkChecksDefinitions")}</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{r.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
  </div>;
}

function CountsRow({ label, counts: c }: { label: string; counts: CollectionCounts }) {
  const { t } = useI18n();
  const unknown = t("studioUnknown");
  return <tr className="border-t"><th className="py-2 text-left">{label}</th><td>{c.enrolled}/{c.planned}</td><td>{c.complete_enrolled}/{c.enrolled}</td><td>{c.missing_purchase}/{c.enrolled} ({rate(c.purchase_missing_rate, unknown)})</td><td>{c.missing_delivery}</td><td>{c.not_delivered}/{c.known_delivery} ({rate(c.non_delivery_rate, unknown)})</td></tr>;
}
