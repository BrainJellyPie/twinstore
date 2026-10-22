// The weeks after a run, with shoppers who remember their visits: how many keep coming under one or two operations
// plans, next to an ideal store (endless stock, no line) that loses only the weekly churn.

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { WeeksReport } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { formatMoney } from "@/shared/utils/money";

const COLORS = ["var(--muted-foreground)", "var(--primary)"];

export function WeeksView({ series, code }: { series: { label: MessageKey; report: WeeksReport }[]; code: string }) {
  const { locale, t } = useI18n();
  const main = series[series.length - 1];
  if (!main) return null;
  const weeks = main.report.weeks;
  const data = weeks.map((week, i) => ({
    week: week.week,
    ideal: week.ideal_shoppers,
    ...Object.fromEntries(series.map((s) => [s.label, s.report.weeks[i]?.shoppers ?? null])),
  }));
  const money = (minor: number) => formatMoney(minor, code, { locale });

  return (
    <div className="space-y-2">
      <p>{t("memSummary", {
        weeks: weeks.length, revenue: money(main.report.revenue), ideal: money(main.report.ideal_revenue),
        lost: money(main.report.lost_to_memory), first: main.report.shoppers_first.toLocaleString(locale),
        last: main.report.shoppers_last.toLocaleString(locale),
      })}</p>
      <div className="h-40 w-full" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="week" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Line type="monotone" dataKey="ideal" name={t("memIdeal")} stroke="var(--chart-3)" strokeDasharray="4 3"
              dot={false} isAnimationActive={false} />
            {series.map((s, i) => (
              <Line key={s.label} type="monotone" dataKey={s.label} name={t(s.label)} stroke={COLORS[i + (series.length === 1 ? 1 : 0)]}
                strokeWidth={2} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div role="region" aria-label={t("memChart")} tabIndex={0} className="overflow-x-auto">
      <table className="w-full tabular-nums [&_td]:px-2 [&_th]:px-2">
        <caption className="sr-only">{t("memChart")}</caption>
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-0.5 text-left font-normal">{t("memWeek")}</th>
            {series.map((s) => <th key={s.label} scope="col" className="py-0.5 text-right font-normal">{t(s.label)}</th>)}
            <th scope="col" className="py-0.5 text-right font-normal">{t("memIdeal")}</th>
            <th scope="col" className="py-0.5 text-right font-normal">{t("memLeftStock")}</th>
            <th scope="col" className="py-0.5 text-right font-normal">{t("memLeftTills")}</th>
          </tr>
        </thead>
        <tbody>
          {weeks.map((week, i) => (
            <tr key={week.week} className="border-t">
              <th scope="row" className="py-0.5 text-left font-normal">{t("memWeekLabel", { week: week.week })}</th>
              {series.map((s) => <td key={s.label} className="py-0.5 text-right">{(s.report.weeks[i]?.shoppers ?? 0).toLocaleString(locale)}</td>)}
              <td className="py-0.5 text-right">{week.ideal_shoppers.toLocaleString(locale)}</td>
              <td className="py-0.5 text-right">{week.left_for_stock.toLocaleString(locale)}</td>
              <td className="py-0.5 text-right">{week.left_for_tills.toLocaleString(locale)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
