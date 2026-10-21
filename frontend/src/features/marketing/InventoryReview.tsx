import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { inventoryExport, inventoryPreview, inventoryTemplateDownload } from "@/services/mutations/inventoryReview";
import type { InventoryFlag } from "@/shared/api/inventoryReview";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

const FLAGS: Record<InventoryFlag, string> = {
  stock_mismatch: "Closing stock does not reconcile", negative_expected_stock: "Expected stock is negative",
  empty_stock_value: "Zero stock has nonzero cost value", net_returns: "Returns exceed units sold",
  zero_supply: "No opening stock or inbound supply", zero_inventory_cost: "Zero average inventory cost", negative_cogs: "Net COGS is negative",
};
const number = (value: number) => (value === 0 ? 0 : value).toLocaleString(undefined, { maximumFractionDigits: 3 });
const ratio = (value: number | null) => value == null ? "Unavailable" : value.toLocaleString(undefined, { maximumSignificantDigits: 8 });
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function InventoryReview({ projectId }: { projectId: string }) {
  const [start, setStart] = useState(""); const [end, setEnd] = useState(""); const [currency, setCurrency] = useState("");
  const [file, setFile] = useState<File>(); const [fileError, setFileError] = useState("");
  const preview = useMutation(inventoryPreview(projectId));
  const audit = useMutation({ ...inventoryExport(projectId), onSuccess: (blob, req) => save(blob, `inventory-${req.start_date}-${req.end_date}.csv`) });
  const template = useMutation({ ...inventoryTemplateDownload(projectId), onSuccess: (blob) => save(blob, "inventory-template.csv") });
  const busy = preview.isPending || audit.isPending || template.isPending;
  const days = (Date.parse(end) - Date.parse(start)) / 86400000 + 1;
  const valid = !!file && /^\d{4}-\d{2}-\d{2}$/.test(start) && /^\d{4}-\d{2}-\d{2}$/.test(end) && days >= 1 && days <= 3660 && /^[A-Z]{3}$/.test(currency);
  const clear = () => { preview.reset(); audit.reset(); template.reset(); };
  const report = preview.data;
  const error = fileError || preview.error?.message || audit.error?.message || template.error?.message;
  return <section aria-label="Inventory performance review" className="space-y-4 rounded-2xl border bg-card p-4">
    <h2 className="text-lg font-semibold">Inventory performance review</h2>
    <p className="text-sm text-muted-foreground">Reconcile recorded stock before interpreting period margin, turnover and net unit sell-through. This uses your observed records, without model calls or inventory write-back.</p>
    <div className="grid gap-3 sm:grid-cols-3">
      <label className="text-sm">Period start (inclusive)<Input type="date" disabled={busy} value={start} onChange={(e) => { clear(); setStart(e.target.value); }} /></label>
      <label className="text-sm">Period end (inclusive)<Input type="date" disabled={busy} value={end} onChange={(e) => { clear(); setEnd(e.target.value); }} /></label>
      <label className="text-sm">Currency code<Input placeholder="USD, KRW, ..." maxLength={3} disabled={busy} value={currency} onChange={(e) => { clear(); setCurrency(e.target.value.toUpperCase()); }} /></label>
    </div>
    <p className="text-xs">Choose 1–3660 days and verify that every row uses the same currency and inventory scope. Money is in integer minor units (USD cents, KRW won), with inventory valued at cost. No currency conversion. Enter every numeric field explicitly; missing is not zero.</p>
    <details><summary className="cursor-pointer text-sm">CSV columns and definitions</summary><div className="space-y-2 text-xs text-muted-foreground">
      <p>sku; opening_units; received_units; sold_units (gross); returned_units (customer returns); other_in_units; other_out_units; closing_units; net_sales_minor; cogs_minor (net of returns); opening_cost_minor; closing_cost_minor.</p>
      <p>Other in/out covers transfers, supplier returns, write-offs and corrections. Use one unit consistently within each SKU. UTF-8, one row per exact SKU, at most 2,000 rows / 2 MB. Quantities: 0–1,000,000 with up to 3 decimals. Net money: ±1,000,000,000,000; stock values: 0–1,000,000,000,000. No personal details.</p>
      <p>Expected closing = opening + received + customer returns + other in − gross sold − other out. A closing difference is an unexplained balance difference, not automatically theft or shrinkage.</p>
    </div></details>
    <Button variant="outline" size="sm" disabled={busy} onClick={() => template.mutate()}>Download inventory template</Button>
    <label className="block text-sm">Inventory CSV<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
      clear(); setFileError(""); const chosen = e.target.files?.[0];
      if (chosen && chosen.size > 2 * 1024 * 1024) { setFile(undefined); setFileError("Inventory CSV exceeds 2 MB"); } else setFile(chosen);
    }} /></label>
    <Button disabled={!valid || busy} onClick={() => { if (file) preview.mutate({ file, start_date: start, end_date: end, currency }); }}>Review inventory</Button>
    {preview.isPending && <p className="text-sm">Reconciling the supplied period records…</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {report && <div className="space-y-3 text-sm">
      <p>{report.period.start_date} to {report.period.end_date} · {report.period_days} days · {report.period.currency} minor units · {report.totals.reconciled_skus} / {report.totals.sku_count} SKUs reconcile.</p>
      <p>Supplied totals: net sales {number(report.totals.net_sales_minor)}; net COGS {number(report.totals.cogs_minor)}; gross profit {number(report.totals.gross_profit_minor)}; average inventory at cost {number(report.totals.average_inventory_cost_minor)}.</p>
      <p>Portfolio period GMROI: <b>{ratio(report.totals.gmroi)}</b> · Period turnover: <b>{ratio(report.totals.inventory_turns)}</b>.</p>
      {report.totals.cogs_minor < 0 && <p>Portfolio turnover is unavailable because net COGS is negative.</p>}
      {report.totals.ratios_withheld && <p>Portfolio ratios are withheld: reconcile every SKU and verify inventory values and a positive average cost. No rows are silently excluded.</p>}
      <p className="text-xs text-muted-foreground">Average cost uses only the opening and closing values. Ratios cover this period, are not annualized and are not profit after labor/rent or evidence of a promotion effect. Full source values and results are retained in the audit CSV.</p>
      <div className="max-h-[32rem] overflow-auto"><table className="w-full text-xs"><caption className="text-left">Net unit sell-through = (sold − returns) / (opening + received + other in). Shown as a ratio, not a percent; no combined ratio across SKUs.</caption><thead><tr className="text-left"><th>SKU</th><th>Expected closing</th><th>Recorded closing</th><th>Difference</th><th>Gross profit</th><th>Net unit sell-through</th><th>Period turns</th><th>Period GMROI</th><th>Review flags</th></tr></thead><tbody>{report.rows.map((r) => <tr key={r.inputs.sku} className="border-t"><th className="py-2 text-left">{r.inputs.sku}</th><td>{number(r.expected_closing_units)}</td><td>{r.inputs.closing_units}</td><td>{number(r.difference_units)}</td><td>{number(r.gross_profit_minor)}</td><td>{ratio(r.net_sell_through)}</td><td>{ratio(r.inventory_turns)}</td><td>{ratio(r.gmroi)}</td><td>{r.flags.map((flag) => FLAGS[flag]).join("; ") || "None"}</td></tr>)}</tbody></table></div>
      <p className="break-all text-xs text-muted-foreground">Source SHA-256: {report.source_sha256}. This review is not saved in the project; retain the export and original CSV.</p>
      <Button variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate(preview.variables); }}>Export inventory audit CSV</Button>
      <details><summary className="cursor-pointer">Inventory method and limitations</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
