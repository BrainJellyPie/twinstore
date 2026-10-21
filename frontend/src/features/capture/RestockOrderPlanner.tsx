import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { AuditReport } from "@/shared/api/client";
import { exportRestockOrder, previewRestockOrder, type RestockOrderItem, type RestockOrderRequest } from "@/shared/api/restockOrder";
import { Button } from "@/shared/components/ui/button";
import { formatMoney } from "@/shared/utils/money";

type NumericField = Exclude<keyof RestockOrderItem, "sku">;
type DraftItem = { sku: string; name: string; included: boolean } & Record<NumericField, string>;
const fields: { key: NumericField; label: string; min: number; max: number }[] = [
  { key: "required_units", label: "Required shelf units", min: 0, max: 1_000_000 },
  { key: "stockroom_units", label: "Available stockroom units", min: 0, max: 1_000_000 },
  { key: "pack_size", label: "Units per pack", min: 1, max: 1_000_000 },
  { key: "pack_cost_minor", label: "Cost per pack (minor units)", min: 0, max: 1_000_000_000_000 },
  { key: "max_packs", label: "Supplier available packs", min: 0, max: 1_000_000 },
  { key: "priority", label: "Priority (1 first)", min: 1, max: 1000 },
];
const validInteger = (value: string, min: number, max: number) => /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) >= min && Number(value) <= max;

export function RestockOrderPlanner({ projectId, report }: { projectId: string; report: AuditReport }) {
  const [items, setItems] = useState<DraftItem[]>(() => {
    const names = new Map<string, string>();
    report.findings.filter((f) => f.kind === "missing" && f.sku).forEach((f) => { if (!names.has(f.sku)) names.set(f.sku, f.name); });
    return [...names].map(([sku, name], index) => ({ sku, name, included: true, required_units: "", stockroom_units: "",
      pack_size: "", pack_cost_minor: "", max_packs: "", priority: String(Math.min(index + 1, 1000)) }));
  });
  const [budget, setBudget] = useState("");
  const [delivery, setDelivery] = useState("0");
  const preview = useMutation({ mutationFn: (request: RestockOrderRequest) => previewRestockOrder(projectId, report.capture_id, report.job_id, request) });
  const download = useMutation({
    mutationFn: (request: RestockOrderRequest) => exportRestockOrder(projectId, report.capture_id, report.job_id, request),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob); const link = document.createElement("a");
      link.href = url; link.download = `${report.job_id}-restock-order.csv`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    },
  });
  if (!items.length) return null;
  const selected = items.filter((item) => item.included);
  const valid = selected.length > 0 && selected.length <= 200 && validInteger(budget, 0, 1_000_000_000_000)
    && validInteger(delivery, 0, 1_000_000_000_000)
    && selected.every((item) => fields.every((field) => validInteger(item[field.key], field.min, field.max)));
  const busy = preview.isPending || download.isPending;
  const invalidate = () => { preview.reset(); download.reset(); };
  const request = (): RestockOrderRequest => ({ currency: report.currency, budget_minor: Number(budget), delivery_fee_minor: Number(delivery),
    items: selected.map((item) => ({ sku: item.sku, required_units: Number(item.required_units), stockroom_units: Number(item.stockroom_units),
      pack_size: Number(item.pack_size), pack_cost_minor: Number(item.pack_cost_minor), max_packs: Number(item.max_packs), priority: Number(item.priority) })) });
  const plan = preview.data;
  return <section aria-label="Restocking quantities and budget" className="space-y-3 rounded-xl border p-3">
    <h4 className="section-title">Restocking quantities and budget</h4>
    <p className="text-xs text-muted-foreground">Enter verified quantities for this audited rack face. Required units mean the additional shelf units needed across all listed levels, not facings or sales forecasts. Allocate available stockroom units first, then whole packs by your priority. No order is placed or inventory reserved.</p>
    <div className="grid gap-2 sm:grid-cols-2">{[{ label: `Purchase budget (${report.currency} minor units)`, value: budget, update: setBudget },
      { label: `One delivery fee (${report.currency} minor units)`, value: delivery, update: setDelivery }].map((field) => <label key={field.label} className="text-xs">{field.label}
        <input type="number" min={0} max={1_000_000_000_000} step={1} value={field.value} disabled={busy} onChange={(e) => { invalidate(); field.update(e.target.value); }} className="mt-1 block w-full rounded border bg-background p-1" />
      </label>)}</div>
    <p className="text-xs">Use whole minor units: for example, USD cents or KRW won. Include taxes in pack costs. Priority starts in audit order; edit it to match your operational needs. Ties use SKU order.</p>
    <div className="max-h-96 space-y-2 overflow-y-auto">{items.map((item, index) => <fieldset key={item.sku} disabled={busy} className="rounded-lg border p-2">
      <legend className="px-1 text-xs font-medium">{item.name || item.sku} · {item.sku}</legend>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={item.included} onChange={(e) => { invalidate(); setItems(items.map((old, i) => i === index ? { ...old, included: e.target.checked } : old)); }} />Include {item.sku}</label>
      {item.included && <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{fields.map((field) => <label key={field.key} className="text-xs">{field.label}
        <input aria-label={`${field.label} · ${item.sku}`} type="number" min={field.min} max={field.max} step={1} value={item[field.key]} onChange={(e) => { invalidate(); setItems(items.map((old, i) => i === index ? { ...old, [field.key]: e.target.value } : old)); }} className="mt-1 block w-full rounded border bg-background p-1" />
      </label>)}</div>}
    </fieldset>)}</div>
    {!valid && <p className="text-xs text-muted-foreground">Select 1–200 SKUs and fill every included quantity and cost with a whole number. Enter 0 explicitly when verified; blank values are unknown.</p>}
    <Button type="button" size="sm" variant="outline" disabled={!valid || busy} onClick={() => preview.mutate(request())}>Calculate restocking quantities</Button>
    {preview.isPending && <p className="text-xs">Calculating stockroom transfers and whole-pack purchases…</p>}
    {(preview.error || download.error) && <p role="alert" className="text-xs text-destructive">{preview.error?.message || download.error?.message}</p>}
    {plan && <div className="space-y-3 text-xs">
      <p><b>Planned spend: {formatMoney(plan.total_cost_minor, plan.currency)}</b> · goods {formatMoney(plan.goods_cost_minor, plan.currency)} · delivery {formatMoney(plan.delivery_charged_minor, plan.currency)} · unspent {formatMoney(plan.remaining_budget_minor, plan.currency)}</p>
      <p>{plan.omitted_skus.length} identified missing SKUs excluded · {plan.unidentified_findings} unidentified missing findings excluded.</p>
      <div className="overflow-x-auto"><table className="w-full"><thead><tr className="text-left"><th>Priority / SKU</th><th>From stockroom</th><th>Packs / units ordered</th><th>Unfilled units</th><th>Surplus units</th><th>Goods cost</th><th>Constraints</th></tr></thead>
        <tbody>{plan.actions.map((action) => <tr key={action.item.sku} className="border-t"><th className="py-2 text-left">{action.item.priority} · {action.item.sku}<span className="block font-normal">Levels {action.levels.join(", ")}</span></th><td>{action.stockroom_used}</td><td>{action.packs_ordered} / {action.units_ordered}</td><td>{action.unfilled_units}</td><td>{action.surplus_units}</td><td>{formatMoney(action.cost_minor, plan.currency)}</td><td>{[action.supplier_limited ? "Supplier limit" : "", action.budget_limited ? "Budget limit" : ""].filter(Boolean).join("; ") || "None"}</td></tr>)}</tbody>
      </table></div>
      <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => { if (preview.variables) download.mutate(preview.variables); }}>Export quantity plan CSV</Button>
      <details><summary className="cursor-pointer">Allocation method and limitations</summary><ul className="mt-2 list-disc space-y-1 pl-5">{plan.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
