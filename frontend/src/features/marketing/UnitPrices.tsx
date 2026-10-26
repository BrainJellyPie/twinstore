import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { unitPriceExport, unitPricePreview, unitPriceTemplateDownload } from "@/services/mutations/unitPrices";
import type { PriceFlag } from "@/shared/api/unitPrices";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const FLAGS: Record<PriceFlag, MessageKey> = { future: "mkUpFlagFuture", stale: "mkUpFlagStale", out_of_stock: "mkUpFlagOutOfStock", unknown_availability: "mkUpFlagUnknown", conditional_offer: "mkUpFlagConditional" };
// Display only: the relation stays the server value everywhere else.
const RELATIONS: Record<string, MessageKey> = { below: "mkUpRelBelow", equal: "mkUpRelEqual", above: "mkUpRelAbove", unavailable: "mkUpRelUnavailable" };
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function UnitPrices({ projectId }: { projectId: string }) {
  const { t } = useI18n();
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
  return <section aria-label={t("mkUpAria")} className="space-y-4 rounded-2xl border bg-card p-4 text-sm">
    <h2 className="text-lg font-semibold">{t("mkUpAria")}</h2>
    <p>{t("mkUpIntro")}</p>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <label>{t("mkFocalRetailer")}<Input disabled={busy} maxLength={120} value={retailer} onChange={(e) => { clear(); setRetailer(e.target.value); }} /></label>
      <label>{t("mkAsOfDate")}<Input type="date" disabled={busy} value={asOf} onChange={(e) => { clear(); setAsOf(e.target.value); }} /></label>
      <label>{t("mkMaxAge")}<Input type="number" min={0} max={365} step={1} disabled={busy} value={age} onChange={(e) => { clear(); setAge(e.target.value); }} /></label>
    </div>
    <p className="text-xs text-muted-foreground">{t("mkUpQualify")}</p>
    <details><summary className="cursor-pointer">{t("mkUpDefinitions")}</summary><div className="space-y-2 text-xs text-muted-foreground">
      <p>{t("mkUpDef1")}</p>
      <p>{t("mkUpDef2")}</p>
      <p>{t("mkUpDef3")}</p>
    </div></details>
    <Button size="sm" variant="outline" disabled={busy} onClick={() => template.mutate(undefined, { onSuccess: (blob) => save(blob, "offer-template.csv") })}>{t("mkUpTemplate")}</Button>
    <label className="block">{t("mkUpCsv")}<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
      clear(); setFileError(""); const chosen = e.target.files?.[0];
      if (chosen && chosen.size > 2 * 1024 * 1024) { setFile(undefined); setFileError(t("mkUpTooLarge")); } else setFile(chosen);
    }} /></label>
    <Button disabled={!valid || busy} onClick={() => { clear(); if (file) preview.mutate({ file, focal_retailer: retailer, as_of: asOf, max_age_days: Number(age) }); }}>{t("mkUpCompare")}</Button>
    {preview.isPending && <p>{t("mkUpReviewing")}</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {report && <div className="space-y-3">
      <p>{t("mkUpSummary", { qualify: report.rows.filter((r) => !r.flags.length).length, total: report.rows.length, retailer: report.scope.focal_retailer, asOf: report.scope.as_of, age: report.scope.max_age_days })}</p>
      <p className="text-xs">{t("mkUpGapHint")}</p>
      <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkUpCaption")}</caption><thead><tr className="text-left"><th>{t("mkColGroupBasis")}</th><th>{t("mkColEligibleOffers")}</th><th>{t("mkColFocalMin")}</th><th>{t("mkColCompetitorMin")}</th><th>{t("mkColGap")}</th><th>{t("mkColGapPct")}</th><th>{t("mkColRelation")}</th><th>{t("mkColMinOffers")}</th></tr></thead><tbody>{report.comparisons.map((c) => <tr key={JSON.stringify([c.comparison_group, c.currency, c.basis])} className="border-t align-top"><th className="py-2 text-left">{c.comparison_group} · {c.currency} / {c.basis}</th><td>{t("mkUpCompetitorRetailers", { focal: c.focal_count, competitor: c.competitor_count, retailers: c.competitor_retailers })}</td><td>{c.focal_min_minor ?? t("studioUnavailable")}</td><td>{c.competitor_min_minor ?? t("studioUnavailable")}</td><td>{c.gap_minor ?? t("studioUnavailable")}</td><td>{c.gap_percent ?? t("studioUnavailable")}</td><td>{Object.prototype.hasOwnProperty.call(RELATIONS, c.relation) ? t(RELATIONS[c.relation]!) : c.relation}</td><td>{t("mkUpFocal", { ids: JSON.stringify(c.focal_offer_ids) })}<br />{t("mkUpCompetitors", { offers: JSON.stringify(c.competitor_offers) })}</td></tr>)}</tbody></table></div>
      <details><summary className="cursor-pointer">{t("mkUpAllOffers")}</summary><div className="max-h-[28rem] overflow-auto"><table className="w-full text-xs"><thead><tr className="text-left"><th>{t("mkColRetailerOffer")}</th><th>{t("mkColGroup")}</th><th>{t("mkColDate")}</th><th>{t("mkColBundle")}</th><th>{t("mkColTotalPrice")}</th><th>{t("mkColUnitPrice")}</th><th>{t("mkColExclusions")}</th></tr></thead><tbody>{report.rows.map((r) => <tr key={JSON.stringify([r.inputs.retailer, r.inputs.offer_id])} className="border-t"><th className="py-2 text-left">{r.inputs.retailer} / {r.inputs.offer_id}</th><td>{r.inputs.comparison_group}</td><td>{r.inputs.observed_on}</td><td>{r.inputs.pack_count} × {r.inputs.quantity_per_pack} {r.inputs.unit}</td><td>{r.inputs.currency} {r.inputs.price_minor}</td><td>{r.unit_price_minor} / {r.basis}</td><td>{r.flags.map((f) => t(FLAGS[f])).join("; ") || t("mkEligibleFlag")}</td></tr>)}</tbody></table></div></details>
      <p className="break-all text-xs">{t("mkUpShaHint", { sha: report.source_sha256 })}</p>
      <Button variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate({ ...preview.variables, source_sha256: report.source_sha256 }, { onSuccess: (blob) => save(blob, "unit-price-audit.csv") }); }}>{t("mkUpExport")}</Button>
      <details><summary className="cursor-pointer">{t("studioMethodLimitations")}</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
