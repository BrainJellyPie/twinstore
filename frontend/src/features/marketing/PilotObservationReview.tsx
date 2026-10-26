import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  getPilotImport, importPilot, pilotHistoryCsvUrl, previewPilotImport,
  type FieldPilot, type ObservationChange, type ObservationDiff, type ObservationPreview, type PilotView,
} from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";
import { Textarea } from "@/shared/components/ui/textarea";
import { useI18n } from "@/shared/i18n/i18n";
import { Input } from "@/shared/components/ui/input";
import { PilotPosReconciliation } from "./PilotPosReconciliation";

export function PilotObservationReview({ projectId, pilot, disabled, onActive, onSaved }: {
  projectId: string; pilot: FieldPilot; disabled: boolean; onActive: (active: boolean) => void;
  onSaved: (result: PilotView) => Promise<void>;
}) {
  const { t } = useI18n();
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
    if (file.size > 2 * 1024 * 1024) { setError(t("mkObsTooLarge")); onActive(false); return; }
    onActive(true); preview.mutate(file);
  };
  return <section className="space-y-3 rounded-xl border p-3">
    <PilotPosReconciliation projectId={projectId} pilot={pilot} disabled={disabled || preview.isPending || apply.isPending || !!review}
      onActive={(active) => { setPosActive(active); onActive(active); }} onReview={startReview} />
    <label className="block text-sm font-medium">{t("mkReviewSheet")}<Input aria-label={t("mkReviewSheet")} type="file" accept=".csv,text/csv" disabled={busy} className="mt-1 max-w-80 font-normal" onChange={(e) => {
      const file = e.target.files?.[0]; e.target.value = "";
      if (!file) return;
      startReview(file);
    }} /></label>
    <p className="text-xs text-muted-foreground">{t("mkReviewSheetHint")}</p>
    {preview.isPending && <p className="text-sm">{t("mkCheckingSheet")}</p>}
    {review && <div className="space-y-3">
      <h4 className="text-sm font-semibold">{t("mkProposedChanges", { revision: String(review.preview.revision), file: review.file.name })}</h4>
      <DiffSummary summary={review.preview.summary} />
      {review.preview.summary.changed_fields ? <>
        <ObservationChanges key={review.preview.review_token} changes={review.preview.changes} />
        <label className="block text-sm">{t("mkImportReason")}<Textarea value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} disabled={busy} placeholder={t("mkImportReasonPlaceholder")} /></label>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} disabled={busy} />{t("mkReviewedChanges")}</label>
        <Button type="button" disabled={busy || !confirmed || !reason.trim()} onClick={() => apply.mutate(review)}>{t("mkApplyObservations")}</Button>
      </> : <p className="text-sm">{t("mkNoValuesChanged")}</p>}
      <Button type="button" variant="ghost" disabled={busy} onClick={() => { setReview(null); setConfirmed(false); preview.reset(); apply.reset(); onActive(false); }}>{t("mkDiscardPreview")}</Button>
    </div>}
    {(error || preview.error || apply.error) && <p role="alert" className="text-sm text-destructive">{error || preview.error?.message || apply.error?.message}</p>}
  </section>;
}

export function PilotImportHistory({ projectId, pilot }: { projectId: string; pilot: FieldPilot }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<number | null>(null);
  const history = pilot.import_history ?? [];
  const audit = useQuery({
    queryKey: ["projects", projectId, "staff-pilots", pilot.pilot_id, "imports", selected],
    queryFn: ({ signal }) => getPilotImport(projectId, pilot.pilot_id, selected!, signal), enabled: selected != null,
  });
  return <details className="space-y-3"><summary className="cursor-pointer text-sm font-semibold">{t("mkImportHistory", { count: history.length })}</summary>
    <p className="text-xs text-muted-foreground">{t("mkImportHistoryHint")}</p>
    {pilot.history_start_revision == null ? <p className="text-sm">{t("mkNoHistoryOld")}</p>
      : pilot.history_start_revision > 0 && <p className="text-sm">{t("mkHistoryStarts", { revision: String(pilot.history_start_revision) })}</p>}
    {history.length === 0 && <p className="text-sm">{t("mkNoImports")}</p>}
    {history.length > 0 && <>
      <Button asChild variant="outline" size="sm"><a href={pilotHistoryCsvUrl(projectId, pilot.pilot_id)} download>{t("mkExportHistory")}</a></Button>
      <div className="space-y-2">{[...history].reverse().map((record) => <div className="rounded-lg border p-2 text-sm" key={record.revision}>
        <Button type="button" size="sm" variant={selected === record.revision ? "secondary" : "ghost"} onClick={() => setSelected(record.revision)}>{t("mkReviewRevision", { revision: String(record.revision) })}</Button>
        <span className="ml-2">{t("mkImportRecord", { at: record.imported_at, assignments: record.summary.changed_assignments, fields: record.summary.changed_fields })}</span>
        <p className="whitespace-pre-wrap">{record.reason}</p>
      </div>)}</div>
      {audit.isFetching && <p className="text-sm">{t("mkLoadingChanges")}</p>}
      {audit.error && <p role="alert" className="text-sm text-destructive">{audit.error.message}</p>}
      {audit.data && <div className="space-y-2"><DiffSummary summary={audit.data.record.summary} /><ObservationChanges key={audit.data.record.revision} changes={audit.data.changes} />
        <p className="break-all text-xs text-muted-foreground">{t("mkUploadedSha", { sha: audit.data.record.source_sha256 })}</p></div>}
    </>}
  </details>;
}

function DiffSummary({ summary: s }: { summary: ObservationDiff }) {
  const { t } = useI18n();
  return <div className="space-y-1 text-sm"><p>{t("mkDiffSummary", { assignments: s.changed_assignments, fields: s.changed_fields, added: s.new_values, corrected: s.corrected_values, cleared: s.cleared_values })}</p>
    {(s.cleared_values > 0 || s.removed_enrollments > 0 || s.purchase_reversals > 0) && <p className="font-semibold">{t("mkChangeFlags", { cleared: s.cleared_values, removed: s.removed_enrollments, reversals: s.purchase_reversals })}</p>}
  </div>;
}

function ObservationChanges({ changes }: { changes: ObservationChange[] }) {
  const { t } = useI18n();
  const [page, setPage] = useState(0);
  const value = (v: boolean | null) => v == null ? t("studioUnknown") : v ? t("studioYes") : t("studioNo");
  return <div className="space-y-2"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColStaffShift")}</th><th>{t("mkColSequenceArm")}</th><th>{t("mkColField")}</th><th>{t("mkColBefore")}</th><th>{t("mkColAfter")}</th></tr></thead>
    <tbody>{changes.slice(page * 100, (page + 1) * 100).map((c) => <tr key={`${c.assignment_id}:${c.field}`} className="border-t"><td className="py-1">{c.staff_id} / {c.shift_id}</td><td>{c.sequence} / {c.arm}</td><td>{c.field}</td><td>{value(c.before)}</td><td>{value(c.after)}</td></tr>)}</tbody>
  </table></div><div className="flex items-center gap-2 text-xs"><Button type="button" size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>{t("mkPrevChanges")}</Button><span>{t("mkChangesRange", { from: page * 100 + 1, to: Math.min((page + 1) * 100, changes.length), total: changes.length })}</span><Button type="button" size="sm" variant="ghost" disabled={(page + 1) * 100 >= changes.length} onClick={() => setPage(page + 1)}>{t("mkNextChanges")}</Button></div></div>;
}
