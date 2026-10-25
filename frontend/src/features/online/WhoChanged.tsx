// Who a change won and who it lost: the paired conversion difference within each segment of the same shoppers, and
// the shoppers whose visit ended differently in the two stores, with where and why each visit ended.

import { useState } from "react";

import type { OnlineRunResult, SegmentDimension, SwitchRow } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { OUTCOME_LABELS, PAGE_LABELS, segmentValueLabel } from "./labels";

const DIMENSIONS: { id: SegmentDimension; label: MessageKey }[] = [
  { id: "mission", label: "onSegMission" }, { id: "device", label: "onSegDevice" },
  { id: "age_group", label: "onSegAge" }, { id: "gender", label: "onSegGender" }, { id: "vision", label: "onSegVision" },
];
const FIRST_SWITCHES = 12;

export function WhoChanged({ result, money, onReplay }: {
  result: OnlineRunResult; money: (x: number) => string; onReplay: (variant: number, shopperId: string) => void;
}) {
  const { t } = useI18n();
  const [dimension, setDimension] = useState<SegmentDimension>("mission");
  const [expanded, setExpanded] = useState(false);
  const control = result.variants[0]?.site_name ?? "";
  const names = new Map(result.shoppers.map((s) => [s.id, s.identity]));
  const points = (x: number) => `${x >= 0 ? "+" : "−"}${(Math.abs(x) * 100).toFixed(1)}${t("onPointsSuffix")}`;
  const signedMoney = (x: number) => `${x >= 0 ? "+" : "−"}${money(Math.abs(x))}`;
  const ending = (outcome: SwitchRow["control_outcome"], total: number, page: SwitchRow["control_exit"]) =>
    `${t(OUTCOME_LABELS[outcome])}${total ? ` · ${money(total)}` : ""} · ${t(PAGE_LABELS[page])}`;
  // Older saved reports have default zero counts but no measured segment analysis.
  if (result.comparisons.every((comparison) => comparison.segments.length === 0)) return null;
  return (
    <section className="panel space-y-3 rounded-[1.4rem] p-4">
      <div>
        <h3 className="text-sm font-semibold">{t("onWho")}</h3>
        <p className="text-xs text-muted-foreground">{t("onWhoHint")}</p>
      </div>
      <div className="inline-flex flex-wrap rounded-md border p-0.5 text-xs" role="group" aria-label={t("onWhoBy")}>
        {DIMENSIONS.map((d) => (
          <button key={d.id} type="button" aria-pressed={dimension === d.id} onClick={() => setDimension(d.id)}
            className={cn("rounded px-2 py-0.5", dimension === d.id ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>{t(d.label)}</button>
        ))}
      </div>
      {result.comparisons.map((c, ci) => {
        const rows = c.segments.filter((s) => s.dimension === dimension);
        const shown = expanded ? c.switches : c.switches.slice(0, FIRST_SWITCHES);
        return (
          <div key={c.site_id} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-medium">{t("onCompareVs", { variant: c.site_name, control })}</span>
              <span className="tone-good rounded-md border px-2 py-0.5 tabular-nums">{t("onWhoWon", { count: c.won })}</span>
              <span className="tone-bad rounded-md border px-2 py-0.5 tabular-nums">{t("onWhoLost", { count: c.lost })}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-xs">
                <thead><tr className="text-left text-muted-foreground">
                  <th className="font-medium">{t(DIMENSIONS.find((d) => d.id === dimension)!.label)}</th>
                  <th className="font-medium">{t("onWhoShoppers")}</th>
                  <th className="font-medium">{control}</th><th className="font-medium">{c.site_name}</th>
                  <th className="font-medium">{t("onWhoDiff")}</th><th className="font-medium">{t("onWhoRevenue")}</th>
                </tr></thead>
                <tbody>
                  {rows.map((s) => {
                    const clear = s.ci_low !== null && s.ci_high !== null && (s.ci_low > 0 || s.ci_high < 0);
                    return (
                      <tr key={s.value} className={cn("border-t", clear && (s.conversion_diff > 0 ? "tone-good" : "tone-bad"))}>
                        <td className="py-1 pr-2">{segmentValueLabel(dimension, s.value, t)}</td>
                        <td className="tabular-nums">{s.n}</td>
                        <td className="tabular-nums">{(s.control_conversion * 100).toFixed(1)}%</td>
                        <td className="tabular-nums">{(s.variant_conversion * 100).toFixed(1)}%</td>
                        <td className="tabular-nums">
                          {points(s.conversion_diff)}
                          {s.ci_low !== null && s.ci_high !== null && (
                            <span className="ml-1 text-muted-foreground">{t("studioCi95", { low: points(s.ci_low), high: points(s.ci_high) })}</span>
                          )}
                        </td>
                        <td className="tabular-nums">{signedMoney(s.revenue_diff)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {c.switches.length === 0 ? <p className="text-xs text-muted-foreground">{t("onWhoNone")}</p> : (
              <div className="space-y-1">
                <div className="text-xs">
                  <span className="font-medium">{t("onWhoSwitched", { count: c.changed })}</span>
                  {c.changed > c.switches.length && <span className="ml-2 text-muted-foreground">{t("onWhoListed", { count: c.switches.length })}</span>}
                </div>
                <ul className="space-y-1">
                  {shown.map((r) => (
                    <li key={r.shopper_id} className="grid gap-1 rounded-lg border p-2 text-xs sm:grid-cols-[160px_minmax(0,1fr)_minmax(0,1fr)]">
                      <span className="font-medium">{names.get(r.shopper_id) ?? r.shopper_id}</span>
                      {([[0, r.control_outcome, r.control_total, r.control_exit, r.control_thought],
                        [ci + 1, r.variant_outcome, r.variant_total, r.variant_exit, r.variant_thought]] as const).map(([variant, outcome, total, page, thought]) => (
                        <div key={variant} className="min-w-0">
                          <div className="flex flex-wrap items-center gap-1">
                            <span className={cn("rounded px-1", outcome === "purchased" ? "tone-good" : "bg-muted")}>{ending(outcome, total, page)}</span>
                            <Button variant="ghost" size="xs" onClick={() => onReplay(variant, r.shopper_id)}
                              aria-label={t("onWhoReplay", { store: variant === 0 ? control : c.site_name })}>{t("onOpenJourney")}</Button>
                          </div>
                          {thought && <p className="truncate italic text-muted-foreground" title={thought}>“{thought}”</p>}
                        </div>
                      ))}
                    </li>
                  ))}
                </ul>
                {c.switches.length > FIRST_SWITCHES && (
                  <Button variant="outline" size="xs" onClick={() => setExpanded((x) => !x)}>
                    {expanded ? t("onWhoFewer") : t("onWhoAll", { count: c.switches.length })}
                  </Button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
