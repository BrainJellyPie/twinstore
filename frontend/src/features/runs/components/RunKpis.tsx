import type { ReactNode } from "react";
import { useState } from "react";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import type { RunSummary } from "@/shared/api/client";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { richText } from "@/shared/i18n/richText";

function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-md border bg-background px-2.5 py-2" title={hint}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}

// Final KPIs of the run (from the backend summary), independent of playback position.
// days: the open days the run's shoppers came on — the totals add those days up.
export function RunKpis({ summary, days }: { summary: RunSummary; days: number }) {
  const { locale, t } = useI18n();
  const code = currencyCode(summary.currency);
  if (summary.conversion_rate === undefined) {
    return (
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {t("kpiOlderRun")}
      </div>
    );
  }
  const figure = (value: string) => <b className="tabular-nums text-foreground">{value}</b>;
  const count = (value: number) => figure(value.toLocaleString(locale));
  return (
    <div className="border-t px-3 py-3">
      <div className="section-title mb-2">{t("kpiRunResults")}</div>
      <p className="mb-2 text-xs text-muted-foreground">
        {days > 1 ? t("kpiTotalsDays", { days }) : t("kpiTotalsOneDay")}
        {richText(t("kpiShoppers"), { count: count(summary.total_customers) })}
        {days > 1 && t("kpiPerDay", { count: Math.round(summary.total_customers / days) })}
        {" · "}{richText(t("kpiRevenue"), { amount: figure(formatMoney(summary.total_revenue, code)) })}
        {summary.units_sold !== undefined && <>{" · "}{richText(t("kpiUnits"), { count: count(summary.units_sold) })}</>}
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Tile label={t("kpiConversion")} value={formatPercent(summary.conversion_rate)} hint={t("kpiConversionHint")} />
        <Tile label={t("kpiRevenuePerVisitor")} value={formatMoney(summary.revenue_per_visitor ?? 0, code)} />
        <Tile label={t("kpiBasketValue")} value={formatMoney(summary.avg_basket_value ?? 0, code)} hint={t("kpiBasketHint")} />
        <Tile label={t("kpiUnitsPerBuyer")} value={(summary.avg_units_per_buyer ?? 0).toFixed(2)} />
        <Tile label={t("dashImpulseShare")} value={formatPercent(summary.impulse_revenue_share ?? 0)} hint={t("dashImpulseHint")} />
        <Tile label={t("kpiAvgVisit")} value={t("kpiSeconds", { seconds: Math.round(summary.avg_visit_sec ?? 0) })}
          hint={t("kpiTilesWalked", { tiles: (summary.avg_path_tiles ?? 0).toFixed(1) })} />
      </div>
      <SegmentBreakdown summary={summary} />
    </div>
  );
}

const DIMENSIONS: { value: string; label: MessageKey }[] = [
  { value: "age_group", label: "kpiAge" },
  { value: "gender", label: "kpiGender" },
  { value: "purpose", label: "kpiPurpose" },
];

function SegmentBreakdown({ summary }: { summary: RunSummary }) {
  const { t } = useI18n();
  const [dimension, setDimension] = useState("age_group");
  const code = currencyCode(summary.currency);
  const rows = Object.entries(summary.segments?.[dimension] ?? {})
    .sort((a, b) => b[1].visitors - a[1].visitors)
    .slice(0, 8);
  if (rows.length === 0) return null;
  const maxRpv = Math.max(...rows.map(([, s]) => s.revenue_per_visitor), 1);

  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-medium text-muted-foreground">{t("kpiBySegment")}</div>
        <ToggleGroup type="single" value={dimension} onValueChange={(v) => v && setDimension(v)} variant="outline" size="sm">
          {DIMENSIONS.map((d) => (
            <ToggleGroupItem key={d.value} value={d.value} className="h-6 px-2 text-xs">
              {t(d.label)}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <ul className="flex flex-col gap-1.5">
        {rows.map(([name, s]) => (
          <li key={name} className="text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate">{name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {t("kpiSegmentLine", { visitors: s.visitors, conversion: formatPercent(s.conversion_rate, 0), perVisitor: formatMoney(s.revenue_per_visitor, code) })}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
              <div className="h-full rounded-full bg-chart-3" style={{ width: `${(s.revenue_per_visitor / maxRpv) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
