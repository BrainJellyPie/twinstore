// A screened change's paired difference in revenue per visit on rule shoppers: clearly better, clearly worse or
// unclear, with conversion and the orders won and lost in its title.

import type { ScanRow } from "@/shared/api/online";
import { cn } from "@/shared/utils/cn";
import { currencyCode, formatMoney } from "@/shared/utils/money";
import { useI18n } from "@/shared/i18n/i18n";

export function ScanChip({ row, currency }: { row: ScanRow | undefined; currency: string }) {
  const { t } = useI18n();
  const revenue = row?.deltas.find((d) => d.metric === "revenue_per_session");
  const conversion = row?.deltas.find((d) => d.metric === "conversion");
  if (!row || !revenue) return null;
  const up = (revenue.ci_low ?? 0) > 0;
  const down = (revenue.ci_high ?? 0) < 0;
  const money = `${revenue.diff >= 0 ? "+" : "−"}${formatMoney(Math.round(Math.abs(revenue.diff)), currencyCode(currency))}`;
  const points = conversion ? `${conversion.diff >= 0 ? "+" : "−"}${Math.abs(conversion.diff * 100).toFixed(1)}${t("onPointsSuffix")}` : "–";
  return (
    <span title={t("onScanChipTitle", { revenue: money, conversion: points, won: row.won, lost: row.lost })}
      className={cn("shrink-0 rounded-full px-1.5 py-0.5 text-[0.7rem] font-medium tabular-nums",
        up ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : down ? "bg-rose-500/15 text-rose-700 dark:text-rose-300"
          : "bg-foreground/[0.06] text-muted-foreground")}>
      {money} · {t(up ? "onScanChipBetter" : down ? "onScanChipWorse" : "onScanChipUnclear")}
    </span>
  );
}
