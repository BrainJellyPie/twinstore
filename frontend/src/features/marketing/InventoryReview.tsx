import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { inventoryExport, inventoryPreview, inventoryTemplateDownload } from "@/services/mutations/inventoryReview";
import type { InventoryFlag } from "@/shared/api/inventoryReview";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { revealOnMount } from "@/shared/utils/focusOnMount";

// The longest review period the server accepts.
const MAX_DAYS = 3660;

const FLAGS: Record<InventoryFlag, MessageKey> = {
  stock_mismatch: "mkInvFlagMismatch", negative_expected_stock: "mkInvFlagNegative",
  empty_stock_value: "mkInvFlagEmptyValue", net_returns: "mkInvFlagNetReturns",
  zero_supply: "mkInvFlagZeroSupply", zero_inventory_cost: "mkInvFlagZeroCost", negative_cogs: "mkInvFlagNegativeCogs",
};
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function InventoryReview({ projectId }: { projectId: string }) {
  const { t, locale } = useI18n();
  const number = (value: number) => (value === 0 ? 0 : value).toLocaleString(locale, { maximumFractionDigits: 3 });
  const ratio = (value: number | null) => value == null ? t("studioUnavailable") : value.toLocaleString(locale, { maximumSignificantDigits: 8 });
  const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [currency, setCurrency] = useState("");
  const [file, setFile] = useState<File>(); const [fileError, setFileError] = useState("");
  const preview = useMutation(inventoryPreview(projectId));
  const audit = useMutation({ ...inventoryExport(projectId), onSuccess: (blob, req) => save(blob, `inventory-${req.start_date}-${req.end_date}.csv`) });
  const template = useMutation({ ...inventoryTemplateDownload(projectId), onSuccess: (blob) => save(blob, "inventory-template.csv") });
  const busy = preview.isPending || audit.isPending || template.isPending;
  const days = (Date.parse(end) - Date.parse(start)) / 86400000 + 1;
  const needsId = useId();
  const valid = !!file && /^\d{4}-\d{2}-\d{2}$/.test(start) && /^\d{4}-\d{2}-\d{2}$/.test(end) && days >= 1 && days <= MAX_DAYS && /^[A-Z]{3}$/.test(currency);
  const clear = () => { preview.reset(); audit.reset(); template.reset(); };
  const report = preview.data;
  const error = fileError || preview.error?.message || audit.error?.message || template.error?.message;
  return <section aria-label={t("mkInvAria")} className="space-y-4 rounded-2xl border bg-card p-4">
    <h2 className="text-lg font-semibold">{t("mkInvAria")}</h2>
    <p className="text-sm text-muted-foreground">{t("mkInvIntro")}</p>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <label className="text-sm">{t("mkPeriodStart")}<Input type="date" disabled={busy} value={start} onChange={(e) => { clear(); setStart(e.target.value); }} /></label>
      <label className="text-sm">{t("mkPeriodEnd")}<Input type="date" disabled={busy} value={end} onChange={(e) => { clear(); setEnd(e.target.value); }} /></label>
      <label className="text-sm">{t("mkCurrencyCode")}<Input placeholder="USD, KRW, ..." maxLength={3} disabled={busy} value={currency} onChange={(e) => { clear(); setCurrency(e.target.value.toUpperCase()); }} /></label>
    </div>
    <p className="text-xs">{t("mkInvRules", { max: MAX_DAYS })}</p>
    <details><summary className="cursor-pointer text-sm">{t("mkInvColumns")}</summary><div className="space-y-2 text-xs text-muted-foreground">
      <p>sku; opening_units; received_units; sold_units (gross); returned_units (customer returns); other_in_units; other_out_units; closing_units; net_sales_minor; cogs_minor (net of returns); opening_cost_minor; closing_cost_minor.</p>
      <p>{t("mkInvColumnsOther")}</p>
      <p>{t("mkInvColumnsFormula")}</p>
    </div></details>
    <Button variant="outline" size="sm" disabled={busy} onClick={() => template.mutate()}>{t("mkInvTemplate")}</Button>
    <label className="block text-sm">{t("mkInvCsv")}<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
      clear(); setFileError(""); const chosen = e.target.files?.[0];
      if (chosen && chosen.size > 2 * 1024 * 1024) { setFile(undefined); setFileError(t("mkInvTooLarge")); } else setFile(chosen);
    }} /></label>
    <Button disabled={!valid || busy} aria-describedby={valid ? undefined : needsId} onClick={() => { if (file) preview.mutate({ file, start_date: start, end_date: end, currency }); }}>{t("mkInvReview")}</Button>
    {!valid && <p id={needsId} className="text-xs text-muted-foreground">{t("mkInvReviewNeeds", { max: MAX_DAYS })}</p>}
    {preview.isPending && <p role="status" className="text-sm">{t("mkInvReconciling")}</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {report && <div className="space-y-3 text-sm">
      <p ref={revealOnMount} tabIndex={-1} className="rounded-md outline-offset-4">{t("mkInvPeriod", { start: report.period.start_date, end: report.period.end_date, days: report.period_days, currency: report.period.currency, reconciled: report.totals.reconciled_skus, total: report.totals.sku_count })}</p>
      <p>{t("mkInvTotals", { sales: number(report.totals.net_sales_minor), cogs: number(report.totals.cogs_minor), profit: number(report.totals.gross_profit_minor), avg: number(report.totals.average_inventory_cost_minor) })}</p>
      <p>{t("mkInvGmroi")} <b>{ratio(report.totals.gmroi)}</b>{t("mkInvTurnover")} <b>{ratio(report.totals.inventory_turns)}</b></p>
      {report.totals.cogs_minor < 0 && <p>{t("mkInvTurnoverUnavailable")}</p>}
      {report.totals.ratios_withheld && <p>{t("mkInvWithheld")}</p>}
      <p className="text-xs text-muted-foreground">{t("mkInvAvgHint")}</p>
      <div className="max-h-[32rem] overflow-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkInvCaption")}</caption><thead><tr className="text-left"><th>{t("mkColSku")}</th><th>{t("mkColExpectedClosing")}</th><th>{t("mkColRecordedClosing")}</th><th>{t("mkColDifference")}</th><th>{t("mkColGrossProfit")}</th><th>{t("mkColSellThrough")}</th><th>{t("mkColTurns")}</th><th>{t("mkColGmroi")}</th><th>{t("mkColFlags")}</th></tr></thead><tbody>{report.rows.map((r) => <tr key={r.inputs.sku} className="border-t"><th className="py-2 text-left">{r.inputs.sku}</th><td>{number(r.expected_closing_units)}</td><td>{r.inputs.closing_units}</td><td>{number(r.difference_units)}</td><td>{number(r.gross_profit_minor)}</td><td>{ratio(r.net_sell_through)}</td><td>{ratio(r.inventory_turns)}</td><td>{ratio(r.gmroi)}</td><td>{r.flags.map((flag) => t(FLAGS[flag])).join("; ") || t("studioNone")}</td></tr>)}</tbody></table></div>
      <p className="break-all text-xs text-muted-foreground">{t("studioSourceSha", { sha: report.source_sha256 })} {t("mkInvNotSaved")}</p>
      <Button variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate(preview.variables); }}>{t("mkInvExport")}</Button>
      <details><summary className="cursor-pointer">{t("mkInvMethod")}</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
