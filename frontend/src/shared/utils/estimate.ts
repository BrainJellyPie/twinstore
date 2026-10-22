// Wording for time and cost estimates (customer writing, simulation runs). Estimates are rough, so every figure
// reads "about": whole minutes under an hour, hours with one decimal above; dollars with two decimals.

import { translate } from "@/shared/i18n/translate";
import type { Locale } from "@/shared/i18n/messages";
import type { RunEstimate } from "@/shared/api/client";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "$1.80"; the backend prices model calls in US dollars whatever the store's currency. */
export function formatUsd(amount: number): string {
  return usd.format(amount);
}

export function durationText(locale: Locale, minutes: number): string {
  const whole = Math.max(1, Math.round(minutes));
  if (whole < 60) return translate(locale, "aboutMinutes", { minutes: whole });
  const hours = new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(minutes / 60);
  return translate(locale, "aboutHours", { hours });
}

/** Free on a local model; "cost unknown" when the server has no price for a cloud model. */
export function costText(locale: Locale, costUsd: number | null, local: boolean): string {
  if (local) return translate(locale, "freeOnThisComputer");
  if (costUsd === null) return translate(locale, "costUnknown");
  if (costUsd > 0 && costUsd < 0.01) return translate(locale, "costUnderCent");
  return translate(locale, "aboutCost", { cost: formatUsd(costUsd) });
}

/** "3,640 shoppers over 7 days (about 520 a day)": a run's or a store's customers as a total over the days. */
export function shoppersOverDaysText(locale: Locale, customers: number, days: number, perDay: number): string {
  return days > 1
    ? translate(locale, "shoppersOverDays", { customers, days, perDay: Math.round(perDay) })
    : translate(locale, "shoppersOneDay", { customers });
}

/** "3,640 shoppers over 7 days (about 520 a day) · about 25 min · about $1.80"; rule-based: "… · about 1 min, no model calls". */
export function runEstimateText(locale: Locale, estimate: RunEstimate): string {
  const shoppers = shoppersOverDaysText(locale, estimate.customers, estimate.days, estimate.per_day);
  const time = durationText(locale, estimate.minutes);
  return estimate.model_calls > 0
    ? [shoppers, time, costText(locale, estimate.cost_usd, estimate.local)].join(" · ")
    : `${shoppers} · ${time}, ${translate(locale, "noModelCalls")}`;
}

/** Report footers: "≈520 visitors a day", or both figures when the simulated customers are a sample of the estimated
 * traffic that per-day money scales by. */
export function visitorsPerDayText(locale: Locale, estimated: number, simulated = 0): string {
  return simulated > 0 && Math.round(simulated) < Math.round(estimated)
    ? translate(locale, "visitorsPerDaySample", { simulated: Math.round(simulated), estimated: Math.round(estimated) })
    : translate(locale, "visitorsPerDayApprox", { count: Math.round(estimated) });
}
