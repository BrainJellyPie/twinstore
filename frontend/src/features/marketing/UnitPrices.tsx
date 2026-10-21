import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { unitPriceExport, unitPricePreview, unitPriceTemplateDownload } from "@/services/mutations/unitPrices";
import type { PriceFlag } from "@/shared/api/unitPrices";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

const FLAGS: Record<PriceFlag, string> = { future: "Future observation", stale: "Too old", out_of_stock: "Out of stock", unknown_availability: "Availability unknown", conditional_offer: "Conditional / member offer" };
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function UnitPrices({ projectId }: { projectId: string }) {
  const [retailer, setRetailer] = useState(""); const [asOf, setAsOf] = useState(""); const [age, setAge] = useState("7");
  const [file, setFile] = useState<File>(); const [fileError, setFileError] = useState("");
  const preview = useMutation(unitPricePreview(projectId));
  const audit = useMutation(unitPriceExport(projectId)); const template = useMutation(unitPriceTemplateDownload(projectId));
  const busy = preview.isPending || audit.isPending || template.isPending;
  const clear = () => { preview.reset(); audit.reset(); template.reset(); };
  const valid = !!file && retailer.length > 0 && retailer === retailer.trim() && /^\d{4}-\d{2}-\d{2}$/.test(asOf)
    && /^\d+$/.test(age) && Number(age) <= 365;
  const report = preview.data;
  const error = fileError || preview.error?.message || audit.error?.message || template.error?.message;
  return <section aria-label="Observed unit-price review" className="space-y-4 rounded-2xl border bg-card p-4 text-sm">
    <h2 className="text-lg font-semibold">Observed unit-price review</h2>
    <p>Compare supplied offers across pack sizes. Use manually verified comparable product groups and consistent tax, deposit, delivery and channel treatment. No live price lookup, model calls or price changes.</p>
    <div className="grid gap-3 sm:grid-cols-3">
      <label>Focal retailer ID<Input disabled={busy} maxLength={120} value={retailer} onChange={(e) => { clear(); setRetailer(e.target.value); }} /></label>
      <label>As-of date<Input type="date" disabled={busy} value={asOf} onChange={(e) => { clear(); setAsOf(e.target.value); }} /></label>
      <label>Maximum observation age (days)<Input type="number" min={0} max={365} step={1} disabled={busy} value={age} onChange={(e) => { clear(); setAge(e.target.value); }} /></label>
    </div>
    <p className="text-xs text-muted-foreground">Only public, in-stock offers dated on or before the as-of date and within 0–365 days qualify. Zero days means the same date only. Separate currencies and quantity dimensions are never combined.</p>
    <details><summary className="cursor-pointer">CSV input definitions</summary><div className="space-y-2 text-xs text-muted-foreground">
      <p>offer_id, comparison_group, retailer, observed_on (YYYY-MM-DD), currency (three uppercase letters), pack_count, quantity_per_pack, unit (g, kg, ml, l, item), price_minor, availability (in_stock, out_of_stock, unknown), terms (public, conditional).</p>
      <p>price_minor is the total payable price for the complete bundle: pack_count × quantity_per_pack. Use integer minor units (USD cents, KRW won), including an explicit zero for a free offer. Mark member, coupon or other eligibility requirements as conditional. Do not enter a per-pack price for a multipack.</p>
      <p>UTF-8 CSV, 1–2,000 rows, at most 2 MB. One observation per exact retailer/offer ID. IDs: 1–120 characters, case-sensitive, no outer whitespace or controls. Pack count: 1–1,000. Quantity per pack: 0.001–1,000,000, up to three decimals; item quantities must be whole counts. Price: 0–1,000,000,000,000. Missing fields are not zero.</p>
    </div></details>
    <Button size="sm" variant="outline" disabled={busy} onClick={() => template.mutate(undefined, { onSuccess: (blob) => save(blob, "offer-template.csv") })}>Download offer template</Button>
    <label className="block">Observed offers CSV<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
      clear(); setFileError(""); const chosen = e.target.files?.[0];
      if (chosen && chosen.size > 2 * 1024 * 1024) { setFile(undefined); setFileError("Offer CSV exceeds 2 MB"); } else setFile(chosen);
    }} /></label>
    <Button disabled={!valid || busy} onClick={() => { clear(); if (file) preview.mutate({ file, focal_retailer: retailer, as_of: asOf, max_age_days: Number(age) }); }}>Compare observed offers</Button>
    {preview.isPending && <p>Reviewing supplied offers…</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {report && <div className="space-y-3">
      <p>{report.rows.filter((r) => !r.flags.length).length} / {report.rows.length} offers qualify · Focal retailer: {report.scope.focal_retailer} · As of {report.scope.as_of} · Maximum age {report.scope.max_age_days} days.</p>
      <p className="text-xs">Each row compares the lowest qualifying focal price with the lowest qualifying competitor price. Gap = focal − competitor, in currency minor units per kg, l or item. Percentage uses the competitor minimum as denominator; a zero denominator is unavailable. A lower observed price does not establish better quality, typical prices, demand or sales effects.</p>
      <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">Observed minima · 12 significant digits; exact arithmetic determines the relation and ties</caption><thead><tr className="text-left"><th>Group / currency / basis</th><th>Eligible focal / competitor offers</th><th>Focal minimum</th><th>Competitor minimum</th><th>Gap</th><th>Gap %</th><th>Relation</th><th>Minimum-price offers</th></tr></thead><tbody>{report.comparisons.map((c) => <tr key={JSON.stringify([c.comparison_group, c.currency, c.basis])} className="border-t align-top"><th className="py-2 text-left">{c.comparison_group} · {c.currency} / {c.basis}</th><td>{c.focal_count} / {c.competitor_count} ({c.competitor_retailers} competitor retailers)</td><td>{c.focal_min_minor ?? "Unavailable"}</td><td>{c.competitor_min_minor ?? "Unavailable"}</td><td>{c.gap_minor ?? "Unavailable"}</td><td>{c.gap_percent ?? "Unavailable"}</td><td>{c.relation}</td><td>Focal: {JSON.stringify(c.focal_offer_ids)}<br />Competitors [retailer, offer]: {JSON.stringify(c.competitor_offers)}</td></tr>)}</tbody></table></div>
      <details><summary className="cursor-pointer">All observed offers and exclusion reasons</summary><div className="max-h-[28rem] overflow-auto"><table className="w-full text-xs"><thead><tr className="text-left"><th>Retailer / offer</th><th>Group</th><th>Date</th><th>Bundle</th><th>Total price (minor)</th><th>Price per base unit (minor)</th><th>Exclusions</th></tr></thead><tbody>{report.rows.map((r) => <tr key={JSON.stringify([r.inputs.retailer, r.inputs.offer_id])} className="border-t"><th className="py-2 text-left">{r.inputs.retailer} / {r.inputs.offer_id}</th><td>{r.inputs.comparison_group}</td><td>{r.inputs.observed_on}</td><td>{r.inputs.pack_count} × {r.inputs.quantity_per_pack} {r.inputs.unit}</td><td>{r.inputs.currency} {r.inputs.price_minor}</td><td>{r.unit_price_minor} / {r.basis}</td><td>{r.flags.map((f) => FLAGS[f]).join("; ") || "Eligible"}</td></tr>)}</tbody></table></div></details>
      <p className="break-all text-xs">Source SHA-256: {report.source_sha256}. Review is not saved; retain the export and original file.</p>
      <Button variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate({ ...preview.variables, source_sha256: report.source_sha256 }, { onSuccess: (blob) => save(blob, "unit-price-audit.csv") }); }}>Export unit-price audit CSV</Button>
      <details><summary className="cursor-pointer">Method and limitations</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
