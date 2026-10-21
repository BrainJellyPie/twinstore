import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { pilotTimingExport, pilotTimingPreview, pilotTimingTemplate } from "@/services/mutations/fieldTiming";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

const seconds = (value: number | null) => value == null ? "Withheld until complete" : value.toLocaleString(undefined, { maximumSignificantDigits: 8 });
function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a");
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function PilotTiming({ projectId, pilotId, revision, eligible }: {
  projectId: string; pilotId: string; revision: number; eligible: boolean;
}) {
  const [file, setFile] = useState<File>();
  const [fileError, setFileError] = useState("");
  const preview = useMutation(pilotTimingPreview(projectId, pilotId));
  const template = useMutation({ ...pilotTimingTemplate(projectId, pilotId),
    onSuccess: (blob) => download(blob, `${pilotId}-staff-time-template.csv`) });
  const audit = useMutation({ ...pilotTimingExport(projectId, pilotId),
    onSuccess: (blob, req) => download(blob, `${pilotId}-staff-time-r${req.revision}.csv`) });
  const busy = preview.isPending || template.isPending || audit.isPending;
  const report = eligible && preview.data?.pilot_id === pilotId && preview.data.revision === revision && preview.variables?.file === file ? preview.data : undefined;
  const error = fileError || preview.error?.message || template.error?.message || audit.error?.message;
  return <section aria-label="Observed staff time" className="space-y-3 rounded-xl border p-3">
    <h4 className="font-semibold">Observed staff time</h4>
    <p className="text-sm text-muted-foreground">Review anonymous timing records before choosing staff-time cost assumptions. This describes supplied records; it does not measure script effectiveness or future staffing needs.</p>
    {!eligible ? <p className="text-sm">Available after closing a fully completed fixed plan. Keep the original stopping rule; do not close early to inspect times.</p> : <>
      <p className="text-xs">Use pilot_id, assignment_id and staff_seconds. Record total active staff time per assigned encounter, including refusals and non-delivery. Use the same timing protocol in both arms. No names, timestamps or customer details.</p>
      <p className="text-xs">Blank or absent means unknown, not zero. Enter 0 only for verified zero time; up to 3600 seconds with three decimal places. Maximum 2 MB and 10,000 rows. Averages remain withheld until every assignment has a time.</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => template.mutate(revision)}>Download staff time template</Button>
      <label className="block space-y-1 text-xs">Staff time CSV<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
        const chosen = e.target.files?.[0]; preview.reset(); audit.reset(); template.reset(); setFileError("");
        if (chosen && chosen.size > 2 * 1024 * 1024) { setFile(undefined); setFileError("Staff time CSV exceeds 2 MB"); }
        else setFile(chosen);
      }} /></label>
      <Button size="sm" variant="outline" disabled={!file || busy} onClick={() => { if (file) preview.mutate({ file, revision }); }}>Review staff time</Button>
      {preview.isPending && <p className="text-sm">Checking staff time against the locked assignments…</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </>}
    {report && <div className="space-y-3 text-sm">
      <p>Timed {report.timed} of {report.planned} assigned encounters · locked revision {report.revision}.</p>
      {!report.complete && <p>Missing times remain unknown. Complete the same timing procedure for both arms before comparing averages.</p>}
      <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="text-left">Time per assigned encounter (seconds; display up to 8 significant digits)</caption><thead><tr className="text-left"><th>Assigned script</th><th>Timed / planned</th><th>Mean seconds</th><th>Maximum seconds</th></tr></thead><tbody>{[report.a, report.b].map((arm) => <tr key={arm.arm} className="border-t"><th className="py-2 text-left">{arm.arm}</th><td>{arm.timed} / {arm.planned}</td><td>{seconds(arm.mean_seconds)}</td><td>{seconds(arm.max_seconds)}</td></tr>)}</tbody></table></div>
      <p>B-minus-A mean time: {seconds(report.difference_seconds)}{report.complete ? " seconds." : "."}</p>
      <details><summary className="cursor-pointer">Staff and shift coverage</summary><ul className="list-disc pl-5 text-xs">{report.blocks.map((b) => <li key={`${b.staff_id}:${b.shift_id}`}>{b.staff_id} / {b.shift_id}: {b.timed} / {b.planned} timed</li>)}</ul></details>
      <p className="break-all text-xs text-muted-foreground">Source SHA-256: {report.source_sha256}. Review is not saved; retain the audit CSV with your source records.</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate(preview.variables); }}>Export staff time audit CSV</Button>
      <details><summary className="cursor-pointer">Timing method and limitations</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
