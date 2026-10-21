import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { priceCheckExport, priceCheckPreview, priceCheckTemplateDownload } from "@/services/mutations/priceChecks";
import type { CheckFlag, PriceObservation } from "@/shared/api/priceChecks";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

const FLAGS: Record<CheckFlag, string> = { missing_label: "Missing label", missing_checkout: "Missing checkout", sku_mismatch: "Different SKU", pack_mismatch: "Different package", currency_mismatch: "Different currency", outside_audit_date: "Outside audit date", terms_unverified: "Conditional or unknown terms" };
const RELATIONS = { checkout_higher: "Checkout higher", checkout_lower: "Checkout lower", equal: "Equal", unavailable: "Unavailable" };
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}
function Observation({ value }: { value: PriceObservation | null }) {
  return value ? <><span>{value.currency} {value.price_minor}</span><br /><span>{value.sku} · {value.pack_reference}</span><br /><span>{value.checked_on} · {value.terms}</span></> : <>Missing observation</>;
}

export function PriceChecks({ projectId }: { projectId: string }) {
  const [store, setStore] = useState(""); const [date, setDate] = useState("");
  const [labels, setLabels] = useState<File>(); const [checkouts, setCheckouts] = useState<File>();
  const [fileErrors, setFileErrors] = useState({ labels: "", checkouts: "" });
  const preview = useMutation(priceCheckPreview(projectId)); const audit = useMutation(priceCheckExport(projectId));
  const template = useMutation(priceCheckTemplateDownload(projectId));
  const busy = preview.isPending || audit.isPending || template.isPending;
  const clear = () => { preview.reset(); audit.reset(); template.reset(); };
  const valid = !!labels && !!checkouts && store.length > 0 && store.length <= 120 && store === store.trim() && /^\d{4}-\d{2}-\d{2}$/.test(date);
  const report = preview.data;
  const error = [fileErrors.labels, fileErrors.checkouts].filter(Boolean).join("; ") || preview.error?.message || audit.error?.message || template.error?.message;
  return <section aria-label="Shelf and checkout price checks" className="space-y-4 rounded-2xl border bg-card p-4 text-sm">
    <h2 className="text-lg font-semibold">Shelf and checkout price checks</h2>
    <p>Reconcile two independently checked observation files. Compare the full payable price of the same item/package, with consistent tax, deposit, channel and timing. This review does not verify your observations or determine legal compliance, refunds or lost sales.</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <label>Store reference<Input disabled={busy} maxLength={120} value={store} onChange={(e) => { clear(); setStore(e.target.value); }} /></label>
      <label>Audit date<Input type="date" disabled={busy} value={date} onChange={(e) => { clear(); setDate(e.target.value); }} /></label>
    </div>
    <details><summary className="cursor-pointer">How to prepare the two files</summary><div className="space-y-2 text-xs text-muted-foreground">
      <p>Use the same template for label and checkout observations: check_id, sku, pack_reference, checked_on (YYYY-MM-DD), currency (three uppercase letters), price_minor, terms (public, conditional, unknown).</p>
      <p>Assign the same check_id to the intended pair. pack_reference identifies the full package/quantity, not its marketing name alone. IDs must match exactly, including case. Repeated SKUs may have separate check IDs; these checks are not independent customers or samples. Do not include personal data.</p>
      <p>price_minor: integer currency minor units (USD cents, KRW won), 0–1,000,000,000,000. Zero explicitly means free, not missing. No decimal rounding, basket, weighted-goods, multibuy or coupon/member arithmetic. Only public terms on both sides qualify.</p>
      <p>UTF-8 CSV; each file at most 2 MB and 2,000 rows. IDs: 1–120 characters without outer whitespace or controls. Each check ID appears once per file. A header-only file is allowed to expose missing observations; at least one observation overall is required. Missing values inside an observation are invalid.</p>
    </div></details>
    <Button size="sm" variant="outline" disabled={busy} onClick={() => template.mutate(undefined, { onSuccess: (blob) => save(blob, "price-check-template.csv") })}>Download price-check template</Button>
    {(["Label observations CSV", "Checkout observations CSV"] as const).map((name, i) => <label className="block" key={name}>{name}<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
      clear(); const chosen = e.target.files?.[0]; const setter = i === 0 ? setLabels : setCheckouts; const key = i === 0 ? "labels" : "checkouts";
      const message = chosen && chosen.size > 2 * 1024 * 1024 ? `${i === 0 ? "Label" : "Checkout"} CSV exceeds 2 MB` : "";
      setFileErrors((previous) => ({ ...previous, [key]: message }));
      setter(message ? undefined : chosen);
    }} /></label>)}
    <Button disabled={!valid || busy} onClick={() => { clear(); if (labels && checkouts) preview.mutate({ labels, checkouts, store_ref: store, audit_date: date }); }}>Review price checks</Button>
    {preview.isPending && <p>Reconciling supplied checks…</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {report && <div className="space-y-3">
      <p>{report.rows.length - report.excluded_count} / {report.rows.length} checks comparable · {report.excluded_count} excluded · {report.label_count} label / {report.checkout_count} checkout observations.</p>
      <p className="break-words">Store: {report.scope.store_ref} · Audit date: {report.scope.audit_date}</p>
      <p className="text-xs">Difference = checkout − label, in integer minor units. Positive and negative sums describe one price per comparable check, without purchase-volume weighting. Net zero can conceal opposing discrepancies. This selected sample is not a store-wide error rate or evidence about staff performance.</p>
      {report.totals.length ? <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Comparable checks by currency</caption><thead><tr className="text-left"><th>Currency</th><th>Comparable</th><th>Higher / lower / equal</th><th>Positive sum</th><th>Negative sum</th><th>Net sum</th></tr></thead><tbody>{report.totals.map((t) => <tr key={t.currency} className="border-t"><th className="py-2 text-left">{t.currency}</th><td>{t.comparable}</td><td>{t.higher} / {t.lower} / {t.equal}</td><td>{t.positive_difference_minor}</td><td>{t.negative_difference_minor}</td><td>{t.net_difference_minor}</td></tr>)}</tbody></table></div> : <p>No comparable pairs. Resolve the exclusions before interpreting prices.</p>}
      <div className="max-h-[28rem] overflow-auto"><table className="w-full text-xs"><caption className="text-left">All supplied checks, including unmatched observations</caption><thead><tr className="text-left"><th>Check ID</th><th>Label</th><th>Checkout</th><th>Difference</th><th>Relation</th><th>Exclusions</th></tr></thead><tbody>{report.rows.map((r) => <tr key={r.check_id} className="border-t align-top"><th className="py-2 text-left">{r.check_id}</th><td><Observation value={r.label} /></td><td><Observation value={r.checkout} /></td><td>{r.difference_minor ?? "Unavailable"}</td><td>{RELATIONS[r.relation]}</td><td>{r.flags.map((f) => FLAGS[f]).join("; ") || "None"}</td></tr>)}</tbody></table></div>
      <p className="break-all text-xs">Sources and scope SHA-256: {report.source_sha256}. Review is not saved; retain the original files and audit.</p>
      <Button variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate({ ...preview.variables, source_sha256: report.source_sha256 }, { onSuccess: (blob) => save(blob, "price-check-audit.csv") }); }}>Export price-check audit CSV</Button>
      <details><summary className="cursor-pointer">Method and limitations</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
