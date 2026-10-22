import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { AuditReport } from "@/shared/api/client";
import { exportRestockOrder, previewRestockOrder, type RestockOrderItem, type RestockOrderRequest } from "@/shared/api/restockOrder";
import { Button } from "@/shared/components/ui/button";
import { formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

type NumericField = Exclude<keyof RestockOrderItem, "sku">;
type DraftItem = { sku: string; name: string; included: boolean } & Record<NumericField, string>;
const fields: { key: NumericField; label: MessageKey; min: number; max: number }[] = [
  { key: "required_units", label: "capOrderRequired", min: 0, max: 1_000_000 },
  { key: "stockroom_units", label: "capOrderStockroom", min: 0, max: 1_000_000 },
  { key: "pack_size", label: "capOrderPackSize", min: 1, max: 1_000_000 },
  { key: "pack_cost_minor", label: "capOrderPackCost", min: 0, max: 1_000_000_000_000 },
  { key: "max_packs", label: "capOrderMaxPacks", min: 0, max: 1_000_000 },
  { key: "priority", label: "capOrderPriority", min: 1, max: 1000 },
];
const validInteger = (value: string, min: number, max: number) => /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) >= min && Number(value) <= max;

export function RestockOrderPlanner({ projectId, report }: { projectId: string; report: AuditReport }) {
  const { t } = useI18n();
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
  return <section aria-label={t("capOrderTitle")} className="space-y-3 rounded-xl border p-3">
    <h4 className="section-title">{t("capOrderTitle")}</h4>
    <p className="text-xs text-muted-foreground">{t("capOrderIntro")}</p>
    <div className="grid gap-2 sm:grid-cols-2">{[{ label: t("capOrderBudget", { currency: report.currency }), value: budget, update: setBudget },
      { label: t("capOrderDelivery", { currency: report.currency }), value: delivery, update: setDelivery }].map((field) => <label key={field.label} className="text-xs">{field.label}
        <input type="number" min={0} max={1_000_000_000_000} step={1} value={field.value} disabled={busy} onChange={(e) => { invalidate(); field.update(e.target.value); }} className="mt-1 block w-full rounded border bg-background p-1" />
      </label>)}</div>
    <p className="text-xs">{t("capOrderUnitsHint")}</p>
    <div className="max-h-96 space-y-2 overflow-y-auto">{items.map((item, index) => <fieldset key={item.sku} disabled={busy} className="rounded-lg border p-2">
      <legend className="px-1 text-xs font-medium">{item.name || item.sku} · {item.sku}</legend>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={item.included} onChange={(e) => { invalidate(); setItems(items.map((old, i) => i === index ? { ...old, included: e.target.checked } : old)); }} />{t("capOrderInclude", { sku: item.sku })}</label>
      {item.included && <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{fields.map((field) => <label key={field.key} className="text-xs">{t(field.label)}
        <input aria-label={`${t(field.label)} · ${item.sku}`} type="number" min={field.min} max={field.max} step={1} value={item[field.key]} onChange={(e) => { invalidate(); setItems(items.map((old, i) => i === index ? { ...old, [field.key]: e.target.value } : old)); }} className="mt-1 block w-full rounded border bg-background p-1" />
      </label>)}</div>}
    </fieldset>)}</div>
    {!valid && <p className="text-xs text-muted-foreground">{t("capOrderInvalid")}</p>}
    <Button type="button" size="sm" variant="outline" disabled={!valid || busy} onClick={() => preview.mutate(request())}>{t("capOrderCalculate")}</Button>
    {preview.isPending && <p className="text-xs">{t("capOrderCalculating")}</p>}
    {(preview.error || download.error) && <p role="alert" className="text-xs text-destructive">{preview.error?.message || download.error?.message}</p>}
    {plan && <div className="space-y-3 text-xs">
      <p><b>{t("capOrderPlannedSpend", { amount: formatMoney(plan.total_cost_minor, plan.currency) })}</b>{t("capOrderSpendBreakdown", { goods: formatMoney(plan.goods_cost_minor, plan.currency), delivery: formatMoney(plan.delivery_charged_minor, plan.currency), unspent: formatMoney(plan.remaining_budget_minor, plan.currency) })}</p>
      <p>{t("capOrderExcluded", { omitted: plan.omitted_skus.length, unidentified: plan.unidentified_findings })}</p>
      <div className="overflow-x-auto"><table className="w-full"><thead><tr className="text-left"><th>{t("capOrderColPriority")}</th><th>{t("capOrderColStockroom")}</th><th>{t("capOrderColOrdered")}</th><th>{t("capOrderColUnfilled")}</th><th>{t("capOrderColSurplus")}</th><th>{t("capOrderColCost")}</th><th>{t("capOrderColConstraints")}</th></tr></thead>
        <tbody>{plan.actions.map((action) => <tr key={action.item.sku} className="border-t"><th className="py-2 text-left">{action.item.priority} · {action.item.sku}<span className="block font-normal">{t("capOrderLevels", { levels: action.levels.join(", ") })}</span></th><td>{action.stockroom_used}</td><td>{action.packs_ordered} / {action.units_ordered}</td><td>{action.unfilled_units}</td><td>{action.surplus_units}</td><td>{formatMoney(action.cost_minor, plan.currency)}</td><td>{[action.supplier_limited ? t("capOrderSupplierLimit") : "", action.budget_limited ? t("capOrderBudgetLimit") : ""].filter(Boolean).join("; ") || t("studioNone")}</td></tr>)}</tbody>
      </table></div>
      <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => { if (preview.variables) download.mutate(preview.variables); }}>{t("capOrderExport")}</Button>
      <details><summary className="cursor-pointer">{t("capOrderMethod")}</summary><ul className="mt-2 list-disc space-y-1 pl-5">{plan.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
