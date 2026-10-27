import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { pilotEconomicsExport, pilotEconomicsPreview } from "@/services/mutations/fieldEconomics";
import type { PilotEconomicsRequest } from "@/shared/api/fieldEconomics";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { currencyCode } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { richText } from "@/shared/i18n/richText";

type Assumption = Exclude<keyof PilotEconomicsRequest, "revision" | "currency">;
const fields: { key: Assumption; label: MessageKey; max: number }[] = [
  { key: "contribution_per_conversion_minor", label: "mkEconContribution", max: 1_000_000_000 },
  { key: "labor_per_hour_minor", label: "mkEconLabor", max: 1_000_000_000 },
  { key: "seconds_per_encounter_a", label: "mkEconSecondsA", max: 3600 },
  { key: "seconds_per_encounter_b", label: "mkEconSecondsB", max: 3600 },
  { key: "eligible_encounters_per_day", label: "mkEconDaily", max: 1_000_000 },
];

export function PilotEconomics({ projectId, pilotId, revision, currency, eligible }: {
  projectId: string; pilotId: string; revision: number; currency: string; eligible: boolean;
}) {
  const { t, locale } = useI18n();
  const number = (value: number) => value.toLocaleString(locale, { maximumSignificantDigits: 8 });
  const points = (value: number) => t("studioPp", { value: number(value * 100) });
  const [draft, setDraft] = useState<Record<Assumption, string>>({ contribution_per_conversion_minor: "", labor_per_hour_minor: "",
    seconds_per_encounter_a: "", seconds_per_encounter_b: "", eligible_encounters_per_day: "" });
  const preview = useMutation(pilotEconomicsPreview(projectId, pilotId));
  const download = useMutation({ ...pilotEconomicsExport(projectId, pilotId), onSuccess: (blob) => {
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = `${pilotId}-cost-scenario-r${revision}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  } });
  const busy = preview.isPending || download.isPending;
  const valid = fields.every(({ key, max }) => /^\d+$/.test(draft[key]) && Number.isSafeInteger(Number(draft[key])) && Number(draft[key]) <= max);
  const request = (): PilotEconomicsRequest => ({ revision, currency,
    contribution_per_conversion_minor: Number(draft.contribution_per_conversion_minor), labor_per_hour_minor: Number(draft.labor_per_hour_minor),
    seconds_per_encounter_a: Number(draft.seconds_per_encounter_a), seconds_per_encounter_b: Number(draft.seconds_per_encounter_b),
    eligible_encounters_per_day: Number(draft.eligible_encounters_per_day) });
  const report = eligible ? preview.data : undefined;
  return <section aria-label={t("mkEconAria")} className="space-y-3 rounded-xl border p-3">
    <h4 className="font-semibold">{t("mkEconAria")}</h4>
    <p className="text-sm text-muted-foreground">{t("mkEconIntro")}</p>
    {!eligible ? <p className="text-sm">{t("mkAfterClosing")}</p> : <>
      <p className="text-xs">{t("mkEconUnitsHint", { currency: currencyCode(currency) })}</p>
      <p className="text-xs">{t("mkEconTimeHint")}</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{fields.map(({ key, label, max }) => <label key={key} className="space-y-1 text-xs">{t(label)}<Input type="number" min={0} max={max} step={1} value={draft[key]} disabled={busy} onChange={(e) => {
        preview.reset(); download.reset(); setDraft({ ...draft, [key]: e.target.value });
      }} /></label>)}</div>
      <Button size="sm" variant="outline" disabled={!valid || busy} onClick={() => preview.mutate(request())}>{t("mkEconCalculate")}</Button>
      {!valid && <p className="text-xs text-muted-foreground">{t("mkEconInvalid")}</p>}
      {preview.isPending && <p role="status" className="text-sm">{t("mkEconCalculating")}</p>}
      {(preview.error || download.error) && <p role="alert" className="text-sm text-destructive">{preview.error?.message || download.error?.message}</p>}
    </>}
    {report && <div className="space-y-3 text-sm">
      <p>{t("mkEconLocked", { revision: String(report.assumptions.revision), encounters: report.planned_encounters, sku: report.target_sku })}</p>
      <p>{t("mkEconConversion", { diff: points(report.conversion_difference), low: points(report.conversion_ci_low), high: points(report.conversion_ci_high) })}</p>
      <p>{richText(t("mkEconLaborLine"), { value: number(report.incremental_labor_minor), breakEven: <b>{report.break_even_difference == null ? t("mkEconUndefined") : points(report.break_even_difference)}</b> })}</p>
      {report.break_even_difference != null && Math.abs(report.break_even_difference) > 1 && <p className="text-xs">{t("mkEconOutside")}</p>}
      <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="text-left">{t("mkEconCaption", { currency: currencyCode(report.assumptions.currency) })}</caption><thead><tr className="text-left"><th>{t("mkColScenario")}</th><th>{t("mkColEstimate")}</th><th>{t("mkColCondLow")}</th><th>{t("mkColCondHigh")}</th></tr></thead><tbody>{[
        { label: t("mkEconPerEncounter"), value: report.per_encounter }, { label: t("mkEconDailyScenario", { count: report.assumptions.eligible_encounters_per_day }), value: report.per_day },
      ].map(({ label, value }) => <tr key={label} className="border-t"><th className="py-2 text-left">{label}</th><td>{number(value.estimate_minor)}</td><td>{number(value.low_minor)}</td><td>{number(value.high_minor)}</td></tr>)}</tbody></table></div>
      <p className="text-xs text-muted-foreground">{t("mkEconRangesHint")}</p>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => { if (preview.variables) download.mutate(preview.variables); }}>{t("mkEconExport")}</Button>
      <details><summary className="cursor-pointer text-sm">{t("mkEconMethod")}</summary><ul className="mt-2 list-disc space-y-2 pl-5 text-xs text-muted-foreground">{report.notes.map((note) => <li key={note}>{note}</li>)}</ul></details>
    </div>}
  </section>;
}
