import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  getPilotImport, importPilot, pilotHistoryCsvUrl, previewPilotImport,
  type FieldPilot, type ObservationChange, type ObservationDiff, type ObservationPreview, type PilotView,
} from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";
import { Textarea } from "@/shared/components/ui/textarea";
import { PilotPosReconciliation } from "./PilotPosReconciliation";

export function PilotObservationReview({ projectId, pilot, disabled, onActive, onSaved }: {
  projectId: string; pilot: FieldPilot; disabled: boolean; onActive: (active: boolean) => void;
  onSaved: (result: PilotView) => Promise<void>;
}) {
  const [review, setReview] = useState<{ file: File; preview: ObservationPreview } | null>(null);
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [posActive, setPosActive] = useState(false);
  const preview = useMutation({
    mutationFn: (file: File) => previewPilotImport(projectId, pilot.pilot_id, file, pilot.revision),
    onSuccess: (data, file) => setReview({ file, preview: data }),
    onError: () => onActive(false),
  });
  const apply = useMutation({
    mutationFn: (selection: { file: File; preview: ObservationPreview }) => importPilot(projectId, pilot.pilot_id,
      selection.file, selection.preview.revision, selection.preview.review_token, reason.trim()),
    onSuccess: async (result) => { await onSaved(result); setReview(null); setConfirmed(false); setReason(""); onActive(false); },
  });
  const busy = disabled || preview.isPending || apply.isPending || posActive;
  const startReview = (file: File, initialReason = "") => {
    setReview(null); setConfirmed(false); setReason(initialReason); setError(""); preview.reset(); apply.reset();
    if (file.size > 2 * 1024 * 1024) { setError("Observation CSV exceeds 2 MB"); onActive(false); return; }
    onActive(true); preview.mutate(file);
  };
  return <section className="space-y-3 rounded-xl border p-3">
    <PilotPosReconciliation projectId={projectId} pilot={pilot} disabled={disabled || preview.isPending || apply.isPending || !!review}
      onActive={(active) => { setPosActive(active); onActive(active); }} onReview={startReview} />
    <label className="block text-sm font-medium">Review full observation sheet<input aria-label="Review full observation sheet" type="file" accept=".csv,text/csv" disabled={busy} className="ml-2 max-w-64 text-xs" onChange={(e) => {
      const file = e.target.files?.[0]; e.target.value = "";
      if (!file) return;
      startReview(file);
    }} /></label>
    <p className="text-xs text-muted-foreground">Selecting a file only previews changes. All assignments and staff/shift identities must match the saved sheet. Blanks clear existing observations; they do not mean “keep the old value”.</p>
    {preview.isPending && <p className="text-sm">Checking the complete sheet…</p>}
    {review && <div className="space-y-3">
      <h4 className="text-sm font-semibold">Proposed changes · revision {review.preview.revision} · {review.file.name}</h4>
      <DiffSummary summary={review.preview.summary} />
      {review.preview.summary.changed_fields ? <>
        <ObservationChanges key={review.preview.review_token} changes={review.preview.changes} />
        <label className="block text-sm">Import reason<Textarea value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} disabled={busy} placeholder="Initial collection, or why these observations were corrected. Do not enter customer names or receipt details." /></label>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} disabled={busy} />I reviewed the changes, including corrections and cleared values.</label>
        <Button type="button" disabled={busy || !confirmed || !reason.trim()} onClick={() => apply.mutate(review)}>Apply reviewed observations</Button>
      </> : <p className="text-sm">No observation values changed. Nothing will be saved and the revision will stay the same.</p>}
      <Button type="button" variant="ghost" disabled={busy} onClick={() => { setReview(null); setConfirmed(false); preview.reset(); apply.reset(); onActive(false); }}>Discard preview</Button>
    </div>}
    {(error || preview.error || apply.error) && <p role="alert" className="text-sm text-destructive">{error || preview.error?.message || apply.error?.message}</p>}
  </section>;
}

export function PilotImportHistory({ projectId, pilot }: { projectId: string; pilot: FieldPilot }) {
  const [selected, setSelected] = useState<number | null>(null);
  const history = pilot.import_history ?? [];
  const audit = useQuery({
    queryKey: ["projects", projectId, "staff-pilots", pilot.pilot_id, "imports", selected],
    queryFn: ({ signal }) => getPilotImport(projectId, pilot.pilot_id, selected!, signal), enabled: selected != null,
  });
  return <details className="space-y-3"><summary className="cursor-pointer text-sm font-semibold">Observation import history ({history.length})</summary>
    <p className="text-xs text-muted-foreground">This records submitted changes and reasons, not proof of purchase or authenticated reviewer identity. Closure is separate from import revisions.</p>
    {pilot.history_start_revision == null ? <p className="text-sm">This older pilot has no import history. Earlier changes cannot be reconstructed here.</p>
      : pilot.history_start_revision > 0 && <p className="text-sm">Import history starts after revision {pilot.history_start_revision}. Earlier changes were not recorded.</p>}
    {history.length === 0 && <p className="text-sm">No recorded observation imports.</p>}
    {history.length > 0 && <>
      <Button asChild variant="outline" size="sm"><a href={pilotHistoryCsvUrl(projectId, pilot.pilot_id)} download>Export import history CSV</a></Button>
      <div className="space-y-2">{[...history].reverse().map((record) => <div className="rounded-lg border p-2 text-sm" key={record.revision}>
        <Button type="button" size="sm" variant={selected === record.revision ? "secondary" : "ghost"} onClick={() => setSelected(record.revision)}>Review revision {record.revision}</Button>
        <span className="ml-2">{record.imported_at} · {record.summary.changed_assignments} assignments · {record.summary.changed_fields} fields</span>
        <p className="whitespace-pre-wrap">{record.reason}</p>
      </div>)}</div>
      {audit.isFetching && <p className="text-sm">Loading recorded changes…</p>}
      {audit.error && <p role="alert" className="text-sm text-destructive">{audit.error.message}</p>}
      {audit.data && <div className="space-y-2"><DiffSummary summary={audit.data.record.summary} /><ObservationChanges key={audit.data.record.revision} changes={audit.data.changes} />
        <p className="break-all text-xs text-muted-foreground">Uploaded CSV SHA-256: {audit.data.record.source_sha256}</p></div>}
    </>}
  </details>;
}

function DiffSummary({ summary: s }: { summary: ObservationDiff }) {
  return <div className="space-y-1 text-sm"><p>{s.changed_assignments} assignments · {s.changed_fields} changed fields: {s.new_values} newly recorded, {s.corrected_values} corrected, {s.cleared_values} cleared to unknown.</p>
    {(s.cleared_values > 0 || s.removed_enrollments > 0 || s.purchase_reversals > 0) && <p className="font-semibold">Change flags: {s.cleared_values} known values cleared; {s.removed_enrollments} enrolled encounters removed; {s.purchase_reversals} purchase outcomes switched between yes and no. Check these corrections against your source records.</p>}
  </div>;
}

function ObservationChanges({ changes }: { changes: ObservationChange[] }) {
  const [page, setPage] = useState(0);
  const value = (v: boolean | null) => v == null ? "Unknown" : v ? "Yes" : "No";
  return <div className="space-y-2"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>Staff / shift</th><th>Sequence / arm</th><th>Field</th><th>Before</th><th>After</th></tr></thead>
    <tbody>{changes.slice(page * 100, (page + 1) * 100).map((c) => <tr key={`${c.assignment_id}:${c.field}`} className="border-t"><td className="py-1">{c.staff_id} / {c.shift_id}</td><td>{c.sequence} / {c.arm}</td><td>{c.field}</td><td>{value(c.before)}</td><td>{value(c.after)}</td></tr>)}</tbody>
  </table></div><div className="flex items-center gap-2 text-xs"><Button type="button" size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous changes</Button><span>Changes {page * 100 + 1}–{Math.min((page + 1) * 100, changes.length)} of {changes.length}</span><Button type="button" size="sm" variant="ghost" disabled={(page + 1) * 100 >= changes.length} onClick={() => setPage(page + 1)}>Next changes</Button></div></div>;
}
