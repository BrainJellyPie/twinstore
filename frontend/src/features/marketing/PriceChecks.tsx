import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { priceCheckExport, priceCheckPreview, priceCheckTemplateDownload } from "@/services/mutations/priceChecks";
import type { CheckFlag, PriceObservation } from "@/shared/api/priceChecks";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { revealOnMount } from "@/shared/utils/focusOnMount";

const FLAGS: Record<CheckFlag, MessageKey> = { missing_label: "mkPcFlagMissingLabel", missing_checkout: "mkPcFlagMissingCheckout", sku_mismatch: "mkPcFlagSku", pack_mismatch: "mkPcFlagPack", currency_mismatch: "mkPcFlagCurrency", outside_audit_date: "mkPcFlagDate", terms_unverified: "mkPcFlagTerms" };
const RELATIONS: Record<string, MessageKey> = { checkout_higher: "mkPcRelHigher", checkout_lower: "mkPcRelLower", equal: "mkPcRelEqual", unavailable: "studioUnavailable" };
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = name;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
}
function Observation({ value }: { value: PriceObservation | null }) {
  const { t } = useI18n();
  return value ? <><span>{value.currency} {value.price_minor}</span><br /><span>{value.sku} · {value.pack_reference}</span><br /><span>{value.checked_on} · {value.terms}</span></> : <>{t("mkMissingObservation")}</>;
}

export function PriceChecks({ projectId }: { projectId: string }) {
  const { t } = useI18n();
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
  return <section aria-label={t("mkPcAria")} className="space-y-4 rounded-2xl border bg-card p-4 text-sm">
    <h2 className="text-lg font-semibold">{t("mkPcAria")}</h2>
    <p>{t("mkPcIntro")}</p>
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <label>{t("mkStoreRef")}<Input disabled={busy} maxLength={120} value={store} onChange={(e) => { clear(); setStore(e.target.value); }} /></label>
      <label>{t("mkAuditDate")}<Input type="date" disabled={busy} value={date} onChange={(e) => { clear(); setDate(e.target.value); }} /></label>
    </div>
    <details><summary className="cursor-pointer">{t("mkPcPrepare")}</summary><div className="space-y-2 text-xs text-muted-foreground">
      <p>{t("mkPcPrepare1")}</p>
      <p>{t("mkPcPrepare2")}</p>
      <p>{t("mkPcPrepare3")}</p>
      <p>{t("mkPcPrepare4")}</p>
    </div></details>
    <Button size="sm" variant="outline" disabled={busy} onClick={() => template.mutate(undefined, { onSuccess: (blob) => save(blob, "price-check-template.csv") })}>{t("mkPcTemplate")}</Button>
    {(["mkPcLabelsCsv", "mkPcCheckoutCsv"] as const).map((name, i) => <label className="block" key={name}>{t(name)}<Input type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => {
      clear(); const chosen = e.target.files?.[0]; const setter = i === 0 ? setLabels : setCheckouts; const key = i === 0 ? "labels" : "checkouts";
      const message = chosen && chosen.size > 2 * 1024 * 1024 ? t(i === 0 ? "mkPcLabelTooLarge" : "mkPcCheckoutTooLarge") : "";
      setFileErrors((previous) => ({ ...previous, [key]: message }));
      setter(message ? undefined : chosen);
    }} /></label>)}
    <Button disabled={!valid || busy} onClick={() => { clear(); if (labels && checkouts) preview.mutate({ labels, checkouts, store_ref: store, audit_date: date }); }}>{t("mkPcReview")}</Button>
    {preview.isPending && <p>{t("mkPcReconciling")}</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {report && <div className="space-y-3">
      <p ref={revealOnMount} tabIndex={-1} className="rounded-md outline-offset-4">{t("mkPcSummary", { comparable: report.rows.length - report.excluded_count, total: report.rows.length, excluded: report.excluded_count, labels: report.label_count, checkouts: report.checkout_count })}</p>
      <p className="break-words">{t("mkPcScope", { store: report.scope.store_ref, date: report.scope.audit_date })}</p>
      <p className="text-xs">{t("mkPcDiffHint")}</p>
      {report.totals.length ? <div className="overflow-x-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkPcByCurrency")}</caption><thead><tr className="text-left"><th>{t("mkColCurrency")}</th><th>{t("mkColComparable")}</th><th>{t("mkColHigherLowerEqual")}</th><th>{t("mkColPositiveSum")}</th><th>{t("mkColNegativeSum")}</th><th>{t("mkColNetSum")}</th></tr></thead><tbody>{report.totals.map((total) => <tr key={total.currency} className="border-t"><th className="py-2 text-left">{total.currency}</th><td>{total.comparable}</td><td>{total.higher} / {total.lower} / {total.equal}</td><td>{total.positive_difference_minor}</td><td>{total.negative_difference_minor}</td><td>{total.net_difference_minor}</td></tr>)}</tbody></table></div> : <p>{t("mkPcNoPairs")}</p>}
      <div className="max-h-[28rem] overflow-auto"><table className="w-full text-xs"><caption className="text-left">{t("mkPcAllChecks")}</caption><thead><tr className="text-left"><th>{t("mkColCheckId")}</th><th>{t("mkColLabel")}</th><th>{t("mkColCheckout")}</th><th>{t("mkColDifference")}</th><th>{t("mkColRelation")}</th><th>{t("mkColExclusions")}</th></tr></thead><tbody>{report.rows.map((r) => <tr key={r.check_id} className="border-t align-top"><th className="py-2 text-left">{r.check_id}</th><td><Observation value={r.label} /></td><td><Observation value={r.checkout} /></td><td>{r.difference_minor ?? t("studioUnavailable")}</td><td>{Object.prototype.hasOwnProperty.call(RELATIONS, r.relation) ? t(RELATIONS[r.relation]!) : r.relation}</td><td>{r.flags.map((f) => t(FLAGS[f])).join("; ") || t("studioNone")}</td></tr>)}</tbody></table></div>
      <p className="break-all text-xs">{t("mkPcShaHint", { sha: report.source_sha256 })}</p>
      <Button variant="outline" disabled={busy} onClick={() => { if (preview.variables) audit.mutate({ ...preview.variables, source_sha256: report.source_sha256 }, { onSuccess: (blob) => save(blob, "price-check-audit.csv") }); }}>{t("mkPcExport")}</Button>
      <details><summary className="cursor-pointer">{t("studioMethodLimitations")}</summary><ul className="list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
