import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getPilotCollection, pilotFollowupCsvUrl, pilotKeys, type CollectionCounts, type PilotCollectionReport } from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";

const rate = (value: number | null) => value == null ? "Unknown" : `${(value * 100).toFixed(1)}%`;

export function PilotCollectionChecks({ projectId, pilotId }: { projectId: string; pilotId: string }) {
  const query = useQuery({ queryKey: pilotKeys.collection(projectId, pilotId), queryFn: ({ signal }) => getPilotCollection(projectId, pilotId, signal) });
  return <section className="space-y-3">
    <Button variant="ghost" size="sm" onClick={() => void query.refetch()} disabled={query.isFetching}>Reload collection checks</Button>
    {query.error && <p role="alert" className="text-sm text-destructive">{query.error.message}</p>}
    {query.isFetching && <p className="text-sm text-muted-foreground">Loading collection checks…</p>}
    {query.data && <CollectionReport key={`${query.data.pilot_id}:${query.data.revision}`} projectId={projectId} report={query.data} />}
  </section>;
}

function CollectionReport({ projectId, report: r }: { projectId: string; report: PilotCollectionReport }) {
  const [block, setBlock] = useState("all");
  const [issue, setIssue] = useState("all");
  const [page, setPage] = useState(0);
  const tasks = r.tasks.filter((t) => (block === "all" || `${t.staff_id}:${t.shift_id}` === block) && (issue === "all" || t.issues.some((i) => i === issue)));
  const blocks = r.blocks.filter((b) => block === "all" || `${b.staff_id}:${b.shift_id}` === block);
  return <div className="space-y-4">
    <header className="space-y-1"><h3 className="font-semibold">{r.name} · collection checks</h3>
      <p className="text-xs text-muted-foreground">Saved revision {r.revision} · {r.updated_at}</p>
      <p className="text-sm">{r.finalized_at ? "Closed and locked. Remaining checks are for review; observations cannot be changed." : "Collection is open. Resolve recording gaps using verified source records."}</p>
      <p className="text-sm">Outcome window: {r.outcome_window}</p>
    </header>
    <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
      <p className="rounded-xl bg-muted/40 p-3">Complete enrolled records: <b>{r.counts.complete_enrolled} / {r.counts.enrolled}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">Unknown purchase outcomes: <b>{r.counts.missing_purchase}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">Unknown script delivery: <b>{r.counts.missing_delivery}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">Enrollment record gaps: <b>{r.recording_gaps}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">Unrecorded tail slots: <b>{r.unrecorded_tail}</b></p>
      <p className="rounded-xl bg-muted/40 p-3">Unused before later enrollment: <b>{r.unused_before_enrolled}</b></p>
    </div>
    <p className="text-sm">{r.counts.enrolled} enrolled · {r.counts.unused} marked unused · {r.counts.planned} planned. {r.can_finalize ? r.target_completed ? "All planned encounters have complete records." : "Recorded slots are settled, but unused slots leave the pilot below target." : "Some slot statuses or enrolled outcomes still need recording before closure."}</p>
    <p className="text-xs text-muted-foreground">Tail slots may be future assignments or unentered records. Recording gaps prompt a check; they do not prove a customer was skipped. Use the saved sample and stopping rule throughout collection.</p>
    <label className="block text-sm">Staff / shift filter<select className="ml-2 rounded-md border bg-background p-2" value={block} onChange={(e) => { setBlock(e.target.value); setPage(0); }}>
      <option value="all">All staff/shifts</option>{r.blocks.map((b) => <option key={`${b.staff_id}:${b.shift_id}`} value={`${b.staff_id}:${b.shift_id}`}>{b.staff_id} / {b.shift_id}</option>)}
    </select></label>
    <div className="space-y-2">{blocks.map((b) => <details className="rounded-xl border p-3" key={`${b.staff_id}:${b.shift_id}`}>
      <summary className="cursor-pointer text-sm font-medium">{b.staff_id} / {b.shift_id} · {b.counts.complete_enrolled}/{b.counts.enrolled} enrolled records complete · {b.counts.missing_purchase} purchase outcomes unknown</summary>
      <p className="my-2 text-xs">Last recorded enrollment status: {b.last_recorded_sequence ?? "None"} · {b.recording_gaps} gaps · {b.unrecorded_tail} unrecorded tail slots · {b.unused_before_enrolled} unused before later enrollment.</p>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Arm</th><th>Enrolled / planned</th><th>Complete / enrolled</th><th>Purchase unknown / enrolled</th><th>Delivery unknown</th><th>Non-delivery / known delivery</th></tr></thead>
        <tbody><CountsRow label="A" counts={b.a} /><CountsRow label="B" counts={b.b} /></tbody>
      </table></div>
      <p className="mt-2 text-xs text-muted-foreground">Purchase-missingness difference B − A: {b.purchase_missing_gap == null ? "Unknown" : `${(b.purchase_missing_gap * 100).toFixed(1)} pp`}. This describes record completeness. Non-delivery includes refusals; retain those encounters in their assigned arm.</p>
    </details>)}</div>
    <section className="space-y-3">
      <h4 className="font-semibold">Follow-up checklist</h4>
      <p className="text-sm">{r.tasks.length} assignments need checking. Record verified corrections in the full observation sheet, then review and apply it under Observations and results. Follow-up CSV is a checklist and cannot replace the observation sheet.</p>
      <div className="flex flex-wrap items-center gap-3"><label className="text-sm">Check type<select className="ml-2 rounded-md border bg-background p-2" value={issue} onChange={(e) => { setIssue(e.target.value); setPage(0); }}>
        <option value="all">All checks</option>{r.guidance.map((g) => <option key={g.issue} value={g.issue}>{g.title}</option>)}
      </select></label><Button asChild variant="outline" size="sm"><a href={pilotFollowupCsvUrl(projectId, r.pilot_id)} download>Download all follow-up checks CSV</a></Button></div>
      <p className="text-xs text-muted-foreground">Download includes all checks at the latest saved revision, regardless of these filters. One assignment may have two checks. No purchase counts or treatment-effect estimates appear in this view.</p>
      {tasks.length ? <><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Staff / shift</th><th>Sequence / arm</th><th>Check and action</th></tr></thead>
        <tbody>{tasks.slice(page * 50, (page + 1) * 50).map((task) => <tr className="border-t align-top" key={task.assignment_id}><td className="py-2">{task.staff_id} / {task.shift_id}</td><td className="py-2">{task.sequence} / {task.arm}</td><td className="space-y-2 py-2">{task.issues.map((code) => {
          const guidance = r.guidance.find((g) => g.issue === code);
          return <p key={code}><b>{guidance?.title ?? code}:</b> {guidance?.action}</p>;
        })}</td></tr>)}</tbody></table></div>
        <div className="flex items-center gap-2 text-xs"><Button type="button" size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous checks</Button><span>Assignments {page * 50 + 1}–{Math.min((page + 1) * 50, tasks.length)} of {tasks.length}</span><Button type="button" size="sm" variant="ghost" disabled={(page + 1) * 50 >= tasks.length} onClick={() => setPage(page + 1)}>Next checks</Button></div>
      </> : <p className="text-sm">No follow-up checks match these filters. Unrecorded tail slots may still need collecting or recording.</p>}
    </section>
    <details><summary className="cursor-pointer text-sm font-semibold">Collection check definitions and limitations</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{r.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
  </div>;
}

function CountsRow({ label, counts: c }: { label: string; counts: CollectionCounts }) {
  return <tr className="border-t"><th className="py-2 text-left">{label}</th><td>{c.enrolled}/{c.planned}</td><td>{c.complete_enrolled}/{c.enrolled}</td><td>{c.missing_purchase}/{c.enrolled} ({rate(c.purchase_missing_rate)})</td><td>{c.missing_delivery}</td><td>{c.not_delivered}/{c.known_delivery} ({rate(c.non_delivery_rate)})</td></tr>;
}
