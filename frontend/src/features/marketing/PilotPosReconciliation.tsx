import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { previewPilotPos, type FieldPilot, type PilotPosPreview, type PosMatchStatus } from "@/shared/api/fieldPilot";
import { Button } from "@/shared/components/ui/button";

const labels: Record<PosMatchStatus, string> = {
  proposed_purchase: "Proposed purchase", already_recorded: "Already recorded", conflicting_purchase: "Conflicts with recorded no",
  not_enrolled: "Not recorded as enrolled", no_target_evidence: "No positive target evidence", unknown_assignment: "Unknown assignment", unlinked: "Unlinked transactions",
};

export function PilotPosReconciliation({ projectId, pilot, disabled, onActive, onReview }: {
  projectId: string; pilot: FieldPilot; disabled: boolean; onActive: (active: boolean) => void;
  onReview: (file: File, reason: string) => void;
}) {
  const [error, setError] = useState("");
  const preview = useMutation({
    mutationFn: (file: File) => previewPilotPos(projectId, pilot.pilot_id, file, pilot.revision),
    onError: () => onActive(false),
  });
  const busy = disabled || preview.isPending;
  return <section className="space-y-3 rounded-xl bg-muted/30 p-3">
    <h4 className="text-sm font-semibold">Reconcile POS purchases</h4>
    <p className="text-xs text-muted-foreground">Use anonymous transaction tokens linked to assignment IDs. Only positive net sales of <b>{pilot.product.sku}</b> within “{pilot.design.outcome_window}” can propose unknown purchases. Missing transactions never mean a nonpurchase.</p>
    <details className="text-xs"><summary className="cursor-pointer">POS CSV format</summary>
      <p className="my-2 break-all font-mono">pilot_id,assignment_id,transaction_id,sku,net_quantity</p>
      <p>UTF-8, up to 2 MB and 10,000 item rows. Use this pilot ID: {pilot.pilot_id}. Aggregate each transaction/SKU to one row, net of returns. Quantities must be nonnegative decimals, at most six decimal places. Use unique anonymous transaction tokens across stores and dates; omit customer/payment details. Leave assignment_id blank for unlinked transactions. SKU matching is exact and case-sensitive. Duplicate checks cover this CSV only; reuse across separate files or pilots is not detected.</p>
    </details>
    <label className="block text-sm">Preview POS CSV<input aria-label="Preview POS CSV" type="file" accept=".csv,text/csv" disabled={busy} className="ml-2 max-w-64 text-xs" onChange={(e) => {
      const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
      preview.reset(); setError("");
      if (file.size > 2 * 1024 * 1024) { setError("POS CSV exceeds 2 MB"); onActive(false); return; }
      onActive(true); preview.mutate(file);
    }} /></label>
    {preview.isPending && <p className="text-sm">Matching transactions without saving observations…</p>}
    {(error || preview.error) && <p role="alert" className="text-sm text-destructive">{error || preview.error?.message}</p>}
    {preview.data && <PosReport key={preview.data.source_sha256} report={preview.data} disabled={busy} onReview={(data) => {
      const file = new File([data.candidate_csv], `${data.pilot_id}-pos-proposals.csv`, { type: "text/csv" });
      preview.reset(); onActive(false);
      onReview(file, `POS reconciliation; source SHA-256 ${data.source_sha256}. Verified target SKU and outcome window.`);
    }} onDiscard={() => { preview.reset(); onActive(false); }} />}
  </section>;
}

function PosReport({ report: r, disabled, onReview, onDiscard }: {
  report: PilotPosPreview; disabled: boolean; onReview: (report: PilotPosPreview) => void; onDiscard: () => void;
}) {
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(0);
  const [verified, setVerified] = useState(false);
  const rows = r.matches.filter((m) => filter === "all" || m.status === filter);
  return <div className="space-y-3 text-sm">
    <p>Revision {r.revision} · {r.source_rows} item rows · {r.transactions} transactions · {r.linked_assignments} linked assignments</p>
    <p><b>{r.proposed_purchases} proposed purchases</b> · {r.enrolled_without_evidence} enrolled encounters without positive target evidence in this file, including previously recorded buyers absent from this extract. This is not a nonbuyer count.</p>
    <label className="block">POS match filter<select className="ml-2 rounded-md border bg-background p-1" value={filter} onChange={(e) => { setFilter(e.target.value); setPage(0); }}>
      <option value="all">All matches</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label} ({r.matches.filter((m) => m.status === value).length})</option>)}
    </select></label>
    {rows.length ? <><div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-left"><th>Assignment / staff / shift</th><th>Transaction tokens</th><th>Target units</th><th>Review status</th></tr></thead>
      <tbody>{rows.slice(page * 50, (page + 1) * 50).map((m) => <tr className="border-t align-top" key={m.assignment_id}><td className="py-2">{m.assignment_id || "Unlinked"}<br />{m.staff_id ?? "Unknown"} / {m.shift_id ?? "Unknown"} · {m.sequence ?? "—"}</td><td className="max-w-64 break-all py-2">{m.transaction_ids.slice(0, 3).join(", ")}{m.transaction_ids.length > 3 && <details><summary>{m.transaction_ids.length - 3} more</summary>{m.transaction_ids.slice(3).join(", ")}</details>}</td><td>{m.target_units}</td><td>{labels[m.status]}</td></tr>)}</tbody>
    </table></div><div className="flex items-center gap-2 text-xs"><Button type="button" size="sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous POS matches</Button><span>Matches {page * 50 + 1}–{Math.min((page + 1) * 50, rows.length)} of {rows.length}</span><Button type="button" size="sm" variant="ghost" disabled={(page + 1) * 50 >= rows.length} onClick={() => setPage(page + 1)}>Next POS matches</Button></div></> : <p>No matches in this category.</p>}
    <p className="text-xs">Only proposed purchases enter the candidate sheet. Conflicts, enrollment, script delivery and all other values stay unchanged. Filters do not change the candidate sheet.</p>
    <label className="flex items-start gap-2"><input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} disabled={disabled} />I verified the target SKU, assignment links and finalized net sales within the saved outcome window.</label>
    <div className="flex flex-wrap gap-2"><Button type="button" disabled={disabled || !verified || !r.proposed_purchases} onClick={() => onReview(r)}>Review proposed purchase changes</Button><Button type="button" variant="ghost" disabled={disabled} onClick={onDiscard}>Discard POS preview</Button></div>
    <p className="break-all text-xs text-muted-foreground">Source CSV SHA-256: {r.source_sha256}. No POS file or match report is saved. The next step previews the full observation changes; it does not apply them.</p>
    <details><summary className="cursor-pointer text-xs">POS matching limitations</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul></details>
  </div>;
}
