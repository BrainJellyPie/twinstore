import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { sensitivityCsvUrl, type SensitivityScope } from "@/shared/api/fieldSensitivity";
import { pilotSensitivityQuery } from "@/services/queries/fieldSensitivity";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { formatPercent, formatDecimal } from "@/shared/utils/money";

const scopes: { key: SensitivityScope; label: MessageKey }[] = [
  { key: "staff", label: "mkSensStaff" },
  { key: "shift", label: "mkSensShift" },
  { key: "block", label: "mkSensBlock" },
];

export function PilotSensitivity({ projectId, pilotId, revision, eligible }: { projectId: string; pilotId: string; revision: number; eligible: boolean }) {
  const { t } = useI18n();
  const points = (value: number | null) => value == null ? t("mkNotEstimable") : t("studioPp", { value: `${value > 0 ? "+" : ""}${formatDecimal(value * 100, 2)}` });
  const [requested, setRequested] = useState(false);
  const query = useQuery(pilotSensitivityQuery(projectId, pilotId, revision, eligible && requested));
  const report = !query.error && requested && eligible ? query.data : undefined;
  return <section aria-label={t("mkSensAria")} className="space-y-3 rounded-xl border p-3">
    <h4 className="font-semibold">{t("mkSensAria")}</h4>
    <p className="text-sm text-muted-foreground">{t("mkSensIntro")}</p>
    {!eligible ? <p className="text-sm">{t("mkSensAfterClosing")}</p> : <>
      <Button variant="outline" size="sm" disabled={query.isFetching} onClick={() => { if (requested) void query.refetch(); else setRequested(true); }}>{requested ? t("mkSensReload") : t("mkSensShow")}</Button>
      {query.isFetching && <p className="text-sm">{t("mkSensLoading")}</p>}
      {query.error && <p role="alert" className="text-sm text-destructive">{query.error.message}</p>}
    </>}
    {report && <div className="space-y-3">
      <p className="text-sm">{t("mkSensFull")} <b>{points(report.difference)}</b>{t("mkSensFullDetail", { encounters: report.planned_encounters, blocks: report.blocks, sku: report.target_sku })}</p>
      <p className="text-xs text-muted-foreground">{t("mkSensLocked", { revision: String(report.revision), at: report.finalized_at })}</p>
      {scopes.map(({ key, label }) => {
        const summary = report.summaries.find((s) => s.scope === key);
        return <details key={key} className="rounded-lg border p-3">
          <summary className="cursor-pointer text-sm font-medium">{t(label)}{summary && t("mkSensOpposite", { opposite: summary.opposite_sign_count, estimable: summary.estimable })}</summary>
          {summary && <p className="my-2 text-xs">{t("mkSensRange", { min: points(summary.minimum), max: points(summary.maximum), change: points(summary.max_absolute_change), unavailable: summary.groups - summary.estimable })}</p>}
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th>{t("mkColExcluded")}</th><th>{t("mkColRemoved")}</th><th>{t("mkColRemaining")}</th><th>{t("mkColAfterRemoval")}</th><th>{t("mkColChangeFull")}</th><th>{t("mkColOpposite")}</th></tr></thead>
            <tbody>{report.groups.filter((group) => group.scope === key).map((group) => <tr key={`${group.staff_id}:${group.shift_id}`} className="border-t"><th className="py-2 text-left">{[group.staff_id, group.shift_id].filter(Boolean).join(" / ")}</th><td>{group.removed_encounters} / {formatPercent(group.removed_weight, 1)}</td><td>{group.remaining_encounters}</td><td>{points(group.difference)}</td><td>{points(group.change)}</td><td>{group.opposite_sign == null ? t("mkNotEstimable") : group.opposite_sign ? t("studioYes") : t("studioNo")}</td></tr>)}</tbody>
          </table></div>
        </details>;
      })}
      <Button asChild variant="outline" size="sm"><a href={sensitivityCsvUrl(projectId, report.pilot_id, report.revision)} download>{t("mkSensExport")}</a></Button>
      <p className="text-xs text-muted-foreground">{t("mkSensExportHint")}</p>
      <details><summary className="cursor-pointer text-sm font-medium">{t("mkSensMethod")}</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
