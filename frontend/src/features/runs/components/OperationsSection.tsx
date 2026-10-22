// What sharing the store did to a run: products that ran out, the line at the tills and how many tills each hour
// needed. Runs whose shoppers each had the store to themselves show nothing here.

import type { ReactNode } from "react";

import type { OperationsReport } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";
import { weekdayLong } from "@/shared/i18n/timeFormat";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";

import { useRunOperations } from "../hooks";
import { OperationsLab } from "./OperationsLab";

const STOCKOUTS_SHOWN = 8;

function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-md border bg-background px-2.5 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-[0.72rem] text-muted-foreground">{hint}</div>}
    </div>
  );
}

export function OperationsSection({ projectId, runId, setupId, currency }: { projectId: string; runId: string; setupId?: string; currency?: string }) {
  const { t } = useI18n();
  const { data, isSuccess } = useRunOperations(projectId, runId);
  if (!isSuccess) return null;
  if (!data) {
    // Shoppers each had the store alone: the lab replays them with real stock and tills.
    return (
      <section className="border-t px-3 py-3" aria-label={t("opsTitle")}>
        <OperationsLab projectId={projectId} runId={runId} setupId={setupId} report={null} currency={currency} />
      </section>
    );
  }
  return <OperationsReportView report={data} currency={currency}
    lab={<OperationsLab projectId={projectId} runId={runId} setupId={setupId} report={data} currency={currency} />} />;
}

export function OperationsReportView({ report, currency, lab }: { report: OperationsReport; currency?: string; lab?: ReactNode }) {
  const { locale, t } = useI18n();
  const code = currencyCode(currency);
  const money = (minor: number) => formatMoney(minor, code, { locale });
  const duration = (seconds: number) => seconds < 90
    ? t("opsSeconds", { seconds: Math.round(seconds).toLocaleString(locale) })
    : t("opsMinutes", { minutes: (seconds / 60).toLocaleString(locale, { maximumFractionDigits: 1 }) });
  const count = (value: number) => value.toLocaleString(locale);
  const target = duration(report.config.target_wait_sec);
  const busiest = report.hours.reduce<OperationsReport["hours"][number] | null>(
    (best, hour) => (best === null || hour.counters_needed > best.counters_needed
      || (hour.counters_needed === best.counters_needed && hour.avg_wait_sec > best.avg_wait_sec) ? hour : best), null);
  const maxWait = Math.max(1, ...report.hours.map((h) => h.avg_wait_sec));

  return (
    <section className="border-t px-3 py-3" aria-labelledby="operations-title">
      <div id="operations-title" className="section-title mb-1">{t("opsTitle")}</div>
      <p className="mb-2 text-xs text-muted-foreground">
        {t("opsSetup", { counters: count(report.counters), stock: count(report.config.stock_per_facing), restocks: count(report.restocks) })}
      </p>
      <div className="grid grid-cols-2 gap-2">
        <Tile label={t("opsLostSales")} value={money(report.lost_revenue)}
          hint={t("opsLostSalesHint", { units: count(report.lost_units) })} />
        <Tile label={t("opsSubstituted")} value={t("opsUnits", { units: count(report.substituted_units) })}
          hint={money(report.substituted_revenue)} />
        <Tile label={t("opsAvgWait")} value={report.counters > 0 ? duration(report.avg_wait_sec) : "—"}
          hint={report.counters > 0 && report.queued > 0
            ? t("opsWaitP90", { wait: duration(report.p90_wait_sec), longest: duration(report.max_wait_sec) }) : undefined} />
        <Tile label={t("opsLeftLine")} value={t("opsLeftLineValue", { count: count(report.abandoned), amount: money(report.abandoned_revenue) })}
          hint={report.counters > 0 ? `${t("opsUtilization")}: ${formatPercent(report.counter_utilization, 0)}` : undefined} />
      </div>
      {(report.config.backroom_per_product != null
        || Object.keys(report.config.backroom_overrides ?? {}).length > 0
        || (report.backroom_units ?? 0) > 0 || (report.refill_short_units ?? 0) > 0) && (
        <div className="mt-2 space-y-1">
          <Tile label={t("opsRefillShort")} value={t("opsUnits", { units: count(report.refill_short_units ?? 0) })}
            hint={t("opsBackroomSetup", { units: count(report.backroom_units ?? 0), deliveries: count(report.deliveries ?? 0) })} />
          {(report.backroom ?? []).slice(0, 5).map((b) => (
            <p key={b.sku} className="text-xs text-muted-foreground">
              {t("opsBackroomDry", { name: b.name || b.sku, day: weekdayLong(b.dry_day, locale), time: b.dry_at.slice(0, 5), units: count(b.short_units) })}
            </p>
          ))}
        </div>
      )}
      {(report.crowd_skipped_units ?? 0) > 0 && (
        <div className="mt-2">
          <Tile label={t("opsCrowdSkipped")} value={money(report.crowd_skipped_revenue ?? 0)}
            hint={t("opsUnits", { units: count(report.crowd_skipped_units ?? 0) })} />
        </div>
      )}
      <p className="mt-2 text-xs text-muted-foreground">{t("opsShoppersHit", { count: count(report.shoppers_hit) })}</p>

      {report.counters === 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">{t("opsNoTills")}</p>
      ) : report.hours.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-medium text-muted-foreground">{t("opsHoursTitle")}</div>
          <table className="w-full text-xs tabular-nums">
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-0.5 text-left font-normal">{t("opsHour")}</th>
                <th scope="col" className="py-0.5 text-right font-normal">{t("opsAtTills")}</th>
                <th scope="col" className="w-2/5 py-0.5 text-left font-normal">{t("opsWaitCol")}</th>
                <th scope="col" className="py-0.5 text-right font-normal">{t("opsLeftCol")}</th>
                <th scope="col" className="py-0.5 text-right font-normal">{t("opsNeededCol")}</th>
              </tr>
            </thead>
            <tbody>
              {report.hours.map((hour) => (
                <tr key={hour.hour} className="border-t">
                  <th scope="row" className="py-1 text-left font-normal">{t("opsHourLabel", { hour: hour.hour })}</th>
                  <td className="py-1 text-right">{count(hour.arrivals)}</td>
                  <td className="py-1 pl-2">
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 flex-1 rounded-full bg-muted">
                        <div className={hour.avg_wait_sec > report.config.target_wait_sec ? "h-full rounded-full bg-destructive" : "h-full rounded-full bg-chart-3"}
                          style={{ width: `${(hour.avg_wait_sec / maxWait) * 100}%` }} />
                      </div>
                      <span className="w-14 shrink-0 text-right">{duration(hour.avg_wait_sec)}</span>
                    </div>
                  </td>
                  <td className="py-1 text-right">{count(hour.abandoned)}</td>
                  <td className={hour.counters_needed > report.counters ? "py-1 text-right font-semibold text-destructive" : "py-1 text-right"}>
                    {count(hour.counters_needed)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {busiest && (
            <p className="mt-2 text-xs">
              {report.counters_needed > report.counters
                ? t("opsAdviceMore", { hour: t("opsHourLabel", { hour: busiest.hour }), needed: count(report.counters_needed), open: count(report.counters), target })
                : t("opsAdviceEnough", { open: count(report.counters), target })}
            </p>
          )}
        </div>
      )}

      <div className="mt-3">
        <div className="mb-1 text-xs font-medium text-muted-foreground">{t("opsStockoutsTitle")}</div>
        {report.stockouts.length === 0 ? (
          <p className="text-xs text-muted-foreground">{t("opsNoStockouts")}</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {report.stockouts.slice(0, STOCKOUTS_SHOWN).map((s) => (
              <li key={`${s.rack_id}:${s.sku}`} className="rounded-md border px-2 py-1.5 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium" title={s.sku}>{s.name || s.sku}</span>
                  <span className="shrink-0 truncate text-muted-foreground">{s.rack_name || s.rack_id}</span>
                </div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 text-muted-foreground tabular-nums">
                  {s.first_out && <span>{t("opsRanOut", { time: s.first_out.slice(0, 5), minutes: duration(s.minutes_out * 60) })}</span>}
                  {s.lost_units > 0 && <span className="text-destructive">{t("opsStockoutLost", { units: count(s.lost_units), amount: money(s.lost_revenue) })}</span>}
                  {s.substituted_units > 0 && <span>{t("opsStockoutReplaced", { units: count(s.substituted_units) })}</span>}
                </div>
              </li>
            ))}
            {report.stockouts.length > STOCKOUTS_SHOWN && (
              <li className="text-xs text-muted-foreground">{t("opsMoreStockouts", { count: count(report.stockouts.length - STOCKOUTS_SHOWN) })}</li>
            )}
          </ul>
        )}
      </div>
      {lab}
    </section>
  );
}
