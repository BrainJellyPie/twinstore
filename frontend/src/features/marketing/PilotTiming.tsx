import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { pilotTimingExport, pilotTimingPreview, pilotTimingTemplate } from "@/services/mutations/fieldTiming";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import { revealOnMount } from "@/shared/utils/focusOnMount";

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a");
  link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function PilotTiming({ projectId, pilotId, revision, eligible }: {
  projectId: string; pilotId: string; revision: number; eligible: boolean;
}) {
  const { t, locale } = useI18n();
  const seconds = (value: number | null) => value == null ? t("mkTimingWithheld") : value.toLocaleString(locale, { maximumSignificantDigits: 8 });
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
  return <section aria-label={t("mkTimingTitle")} className="space-y-3 rounded-xl border p-3">
    <h4 className="font-semibold">{t("mkTimingTitle")}</h4>
    <p className="text-sm text-muted-foreground">{t("mkTimingIntro")}</p>
    {!eligible ? <p className="text-sm">{t("mkTimingAfterClosing")}</p> : <>
      <p className="text-xs">{t("mkTimingColumns")}</p>
      <p className="text-xs">{t("mkTimingRules")}</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => template.mutate(revision)}>{t("mkTimingTemplate")}</Button>
      <label className="block space-y-1 text-xs">{t("mkTimingCsv")}<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
        const chosen = e.target.files?.[0]; preview.reset(); audit.reset(); template.reset(); setFileError("");
        if (chosen && chosen.size > 2 * 1024 * 1024) { setFile(undefined); setFileError(t("mkTimingTooLarge")); }
        else setFile(chosen);
      }} /></label>
      <Button size="sm" variant="outline" disabled={!file || busy} onClick={() => { if (file) preview.mutate({ file, revision }); }}>{t("mkTimingReview")}</Button>
      {preview.isPending && <p className="text-sm">{t("mkTimingChecking")}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </>}
    {report && <div className="space-y-3 text-sm">
      <p ref={revealOnMount} tabIndex={-1} className="rounded-md outline-offset-4">{t("mkTimingTimed", { timed: report.timed, planned: report.planned, revision: String(report.revision) })}</p>
      {!report.complete && <p>{t("mkTimingMissing")}</p>}
      <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="text-left">{t("mkTimingCaption")}</caption><thead><tr className="text-left"><th>{t("mkColAssignedScript")}</th><th>{t("mkColTimedPlanned")}</th><th>{t("mkColMeanSeconds")}</th><th>{t("mkColMaxSeconds")}</th></tr></thead><tbody>{[report.a, report.b].map((arm) => <tr key={arm.arm} className="border-t"><th className="py-2 text-left">{arm.arm}</th><td>{arm.timed} / {arm.planned}</td><td>{seconds(arm.mean_seconds)}</td><td>{seconds(arm.max_seconds)}</td></tr>)}</tbody></table></div>
      <p>{t("mkTimingDiff", { value: seconds(report.difference_seconds) })}{report.complete ? t("mkTimingSecondsSuffix") : "."}</p>
      <details><summary className="cursor-pointer">{t("mkTimingCoverage")}</summary><ul className="list-disc pl-5 text-xs">{report.blocks.map((b) => <li key={`${b.staff_id}:${b.shift_id}`}>{t("mkTimingBlock", { block: `${b.staff_id} / ${b.shift_id}`, timed: b.timed, planned: b.planned })}</li>)}</ul></details>
      <p className="break-all text-xs text-muted-foreground">{t("studioSourceSha", { sha: report.source_sha256 })} {t("mkTimingRetain")}</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate(preview.variables); }}>{t("mkTimingExport")}</Button>
      <details><summary className="cursor-pointer">{t("mkTimingMethod")}</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
