import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { factorialExport, factorialPreview } from "@/services/mutations/factorial";
import { factorialSourceQuery } from "@/services/queries/factorial";
import type { FactorialMetric } from "@/shared/api/factorial";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const METRICS: Record<FactorialMetric, MessageKey> = { spend: "mkFactMetricSpend", units: "mkFactMetricUnits", bought: "mkFactMetricBought" };

export function FactorialReview({ projectId, experimentId }: { projectId: string; experimentId: string }) {
  const { t, locale } = useI18n();
  const format = (n: number | null) => n == null ? t("studioUnavailable") : (n === 0 ? 0 : n).toLocaleString(locale, { maximumSignificantDigits: 8 });
  const [open, setOpen] = useState(false);
  const [price, setPrice] = useState(""); const [sign, setSign] = useState(""); const [both, setBoth] = useState("");
  const [metric, setMetric] = useState<FactorialMetric>("spend");
  const source = useQuery(factorialSourceQuery(projectId, experimentId, open));
  const preview = useMutation(factorialPreview(projectId, experimentId));
  const audit = useMutation(factorialExport(projectId, experimentId));
  const busy = source.isFetching || preview.isPending || audit.isPending;
  const clear = () => { preview.reset(); audit.reset(); };
  const report = preview.data?.request.source_sha256 === source.data?.source_sha256 ? preview.data : undefined;
  const valid = source.data?.available && !source.isError && source.data.price_arms.includes(price)
    && source.data.sign_arms.includes(sign) && source.data.combined_arms.includes(both) && new Set([price, sign, both]).size === 3;
  const error = source.error?.message || preview.error?.message || audit.error?.message;
  const exportCsv = () => {
    if (!report) return;
    audit.mutate(report.request, { onSuccess: (blob) => {
      const url = URL.createObjectURL(blob); const link = document.createElement("a");
      link.href = url; link.download = `${experimentId}-factorial.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
    } });
  };
  return <section aria-label={t("mkFactAria")} className="space-y-3 rounded-2xl border bg-card p-4 text-sm">
    <Button variant="outline" onClick={() => setOpen(!open)}>{open ? t("mkFactHide") : t("mkFactOpen")}</Button>
    {open && <>
      <h3 className="font-semibold">{t("mkFactTitle")}</h3>
      <p>{t("mkFactIntro")}</p>
      <p className="text-xs text-muted-foreground">{t("mkFactRules")}</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => { clear(); void source.refetch(); }}>{t("mkFactReload")}</Button>
      {source.isFetching && <p>{t("mkFactLoading")}</p>}
      {source.data && !source.data.available && <p>{source.data.reason}</p>}
      {source.data?.available && <>
        <div className="grid gap-3 sm:grid-cols-3">
          {([
            ["mkFactPriceArm", price, setPrice, source.data.price_arms],
            ["mkFactSignArm", sign, setSign, source.data.sign_arms],
            ["mkFactCombinedArm", both, setBoth, source.data.combined_arms],
          ] as const).map(([label, value, setter, options]) => <label key={label}>{t(label)}<select aria-label={t(label)} className="mt-1 block w-full rounded border bg-background p-2" disabled={busy} value={value} onChange={(e) => { clear(); setter(e.target.value); }}>
            <option value="">{t("mkFactChooseArm")}</option>{options.map((name) => <option key={name} value={name}>{name}</option>)}
          </select></label>)}
        </div>
        <label className="block">{t("mkFactOutcome")}<select aria-label={t("mkFactOutcomeLabel")} className="ml-2 rounded border bg-background p-2" disabled={busy} value={metric} onChange={(e) => { clear(); setMetric(e.target.value as FactorialMetric); }}>
          <option value="spend">{t("mkFactSpend")}</option><option value="units">{t("mkFactUnits")}</option><option value="bought">{t("mkFactBought")}</option>
        </select></label>
        <p className="text-xs">{t("mkFactExploratory")}</p>
        <Button disabled={!valid || busy} onClick={() => { clear(); if (source.data) preview.mutate({ source_sha256: source.data.source_sha256, price_arm: price, sign_arm: sign, combined_arm: both, metric }); }}>{t("mkFactCalculate")}</Button>
      </>}
      {preview.isPending && <p>{t("mkFactCalculating")}</p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
      {report && <div className="space-y-3">
        <p>{t("mkFactCoverage", {
          complete: report.complete_panel, sampled: report.sampled_panel, requested: report.requested_panel,
          metric: Object.prototype.hasOwnProperty.call(METRICS, report.request.metric) ? t(METRICS[report.request.metric]) : report.request.metric,
          unit: report.request.metric === "spend" ? t("mkFactMinorUnits", { currency: report.currency }) : "",
        })}</p>
        {!report.intervals_available && <p>{t("mkFactWithheld")}</p>}
        <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkFactCellsCaption")}</caption><thead><tr className="text-left"><th>{t("mkColCell")}</th><th>{t("mkColArmShort")}</th><th>{t("mkColAvailable")}</th><th>{t("mkColMean")}</th></tr></thead><tbody>{report.cells.map((c) => <tr key={c.cell}><td>{c.cell}</td><td>{c.arm}</td><td>{c.available}</td><td>{format(c.mean)}</td></tr>)}</tbody></table></div>
        <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkFactContrastsCaption")}</caption><thead><tr className="text-left"><th>{t("mkColContrast")}</th><th>{t("mkColEstimate")}</th><th>{t("mkColAdjusted")}</th><th>{t("mkColFormula")}</th></tr></thead><tbody>{report.contrasts.map((c) => <tr key={c.name}><th className="py-2 text-left">{c.name}</th><td>{format(c.estimate)}</td><td>{c.ci_low == null || c.ci_high == null ? t("studioUnavailable") : `[${format(c.ci_low)}, ${format(c.ci_high)}]`}</td><td>{c.formula}</td></tr>)}</tbody></table></div>
        <p className="break-all text-xs">{t("mkFactSha", { sha: report.request.source_sha256 })}</p>
        <Button variant="outline" disabled={busy || source.isError} onClick={exportCsv}>{t("mkFactExport")}</Button>
        <details><summary className="cursor-pointer">{t("studioMethodLimitations")}</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
      </div>}
    </>}
  </section>;
}
