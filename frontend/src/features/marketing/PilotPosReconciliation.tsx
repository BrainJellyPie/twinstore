import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { previewPilotPos, type FieldPilot, type PilotPosPreview, type PosMatchStatus } from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { richText } from "@/shared/i18n/richText";
import { Input } from "@/shared/components/ui/input";

const labels: Record<PosMatchStatus, MessageKey> = {
  proposed_purchase: "mkPosProposed", already_recorded: "mkPosAlready", conflicting_purchase: "mkPosConflict",
  not_enrolled: "mkPosNotEnrolled", no_target_evidence: "mkPosNoEvidence", unknown_assignment: "mkPosUnknownAssignment", unlinked: "mkPosUnlinked",
};

export function PilotPosReconciliation({ projectId, pilot, disabled, onActive, onReview }: {
  projectId: string; pilot: FieldPilot; disabled: boolean; onActive: (active: boolean) => void;
  onReview: (file: File, reason: string) => void;
}) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  const preview = useMutation({
    mutationFn: (file: File) => previewPilotPos(projectId, pilot.pilot_id, file, pilot.revision),
    onError: () => onActive(false),
  });
  const busy = disabled || preview.isPending;
  return <section className="space-y-3 rounded-xl bg-muted/30 p-3">
    <h4 className="text-sm font-semibold">{t("mkPosTitle")}</h4>
    <p className="text-xs text-muted-foreground">{richText(t("mkPosIntro"), { sku: <b>{pilot.product.sku}</b>, window: pilot.design.outcome_window })}</p>
    <details className="text-xs"><summary className="cursor-pointer">{t("mkPosFormat")}</summary>
      <p className="my-2 break-all font-mono">pilot_id,assignment_id,transaction_id,sku,net_quantity</p>
      <p>{t("mkPosFormatHint", { id: pilot.pilot_id })}</p>
    </details>
    <label className="block text-sm">{t("mkPosPreview")}<Input aria-label={t("mkPosPreview")} type="file" accept=".csv,text/csv" disabled={busy} className="mt-1 max-w-80" onChange={(e) => {
      const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
      preview.reset(); setError("");
      if (file.size > 2 * 1024 * 1024) { setError(t("mkPosTooLarge")); onActive(false); return; }
      onActive(true); preview.mutate(file);
    }} /></label>
    {preview.isPending && <p className="text-sm">{t("mkPosMatching")}</p>}
    {(error || preview.error) && <p role="alert" className="text-sm text-destructive">{error || preview.error?.message}</p>}
    {preview.data && <PosReport key={preview.data.source_sha256} report={preview.data} disabled={busy} onReview={(data) => {
      const file = new File([data.candidate_csv], `${data.pilot_id}-pos-proposals.csv`, { type: "text/csv" });
      preview.reset(); onActive(false);
      onReview(file, t("mkPosReviewReason", { sha: data.source_sha256 }));
    }} onDiscard={() => { preview.reset(); onActive(false); }} />}
  </section>;
}

function PosReport({ report: r, disabled, onReview, onDiscard }: {
  report: PilotPosPreview; disabled: boolean; onReview: (report: PilotPosPreview) => void; onDiscard: () => void;
}) {
  const { t } = useI18n();
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(0);
  const [verified, setVerified] = useState(false);
  const rows = r.matches.filter((m) => filter === "all" || m.status === filter);
  return <div className="space-y-3 text-sm">
    <p>{t("mkPosSummary", { revision: String(r.revision), rows: r.source_rows, transactions: r.transactions, linked: r.linked_assignments })}</p>
    <p><b>{t("mkPosProposedCount", { count: r.proposed_purchases })}</b>{t("mkPosWithoutEvidence", { count: r.enrolled_without_evidence })}</p>
    <label className="block">{t("mkPosFilter")}<select className="ml-2 rounded-md border bg-background p-1" value={filter} onChange={(e) => { setFilter(e.target.value); setPage(0); }}>
      <option value="all">{t("mkAllMatches")}</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{t(label)} ({r.matches.filter((m) => m.status === value).length})</option>)}
    </select></label>
    {rows.length ? <><div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-left"><th>{t("mkColAssignmentStaffShift")}</th><th>{t("mkColTokens")}</th><th>{t("mkColTargetUnits")}</th><th>{t("mkColReviewStatus")}</th></tr></thead>
      <tbody>{rows.slice(page * 50, (page + 1) * 50).map((m) => <tr className="border-t align-top" key={m.assignment_id}><td className="py-2">{m.assignment_id || t("mkUnlinked")}<br />{m.staff_id ?? t("studioUnknown")} / {m.shift_id ?? t("studioUnknown")} · {m.sequence ?? "—"}</td><td className="max-w-64 break-all py-2">{m.transaction_ids.slice(0, 3).join(", ")}{m.transaction_ids.length > 3 && <details><summary>{t("mkMoreCount", { count: m.transaction_ids.length - 3 })}</summary>{m.transaction_ids.slice(3).join(", ")}</details>}</td><td>{m.target_units}</td><td>{t(labels[m.status])}</td></tr>)}</tbody>
    </table></div><div className="flex items-center gap-2 text-xs"><Button type="button" size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>{t("mkPrevPos")}</Button><span>{t("mkMatchesRange", { from: page * 50 + 1, to: Math.min((page + 1) * 50, rows.length), total: rows.length })}</span><Button type="button" size="sm" variant="ghost" disabled={(page + 1) * 50 >= rows.length} onClick={() => setPage(page + 1)}>{t("mkNextPos")}</Button></div></> : <p>{t("mkNoMatchesCategory")}</p>}
    <p className="text-xs">{t("mkPosCandidateHint")}</p>
    <label className="flex items-start gap-2"><input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} disabled={disabled} />{t("mkPosVerified")}</label>
    <div className="flex flex-wrap gap-2"><Button type="button" disabled={disabled || !verified || !r.proposed_purchases} onClick={() => onReview(r)}>{t("mkPosReview")}</Button><Button type="button" variant="ghost" disabled={disabled} onClick={onDiscard}>{t("mkPosDiscard")}</Button></div>
    <p className="break-all text-xs text-muted-foreground">{t("mkPosShaHint", { sha: r.source_sha256 })}</p>
    <details><summary className="cursor-pointer text-xs">{t("mkPosLimitations")}</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul></details>
  </div>;
}
