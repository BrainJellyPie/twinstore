import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useI18n } from "@/shared/i18n/i18n";
import { formatPercent } from "@/shared/utils/money";

// legacyRun: the run predates conversion KPIs, so no conversion figure is shown.
export function CustomerBehavior({ legacyRun = false }: { legacyRun?: boolean }) {
  const { t } = useI18n();
  const entered = useSimulationMetricsStore((s) => s.entered);
  const inStore = useSimulationMetricsStore((s) => s.inStore);
  const paidCount = useSimulationMetricsStore((s) => s.paidCount);
  const conversionRate = entered > 0 ? paidCount / entered : 0;

  return (
    <div className="px-3 pb-3">
      <dl className="grid grid-cols-3 gap-2">
        <div className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3">
          <dt className="eyebrow">{t("dashVisitors")}</dt>
          <dd className="num mt-1 text-xl font-medium tracking-[-0.04em]">{entered}</dd>
        </div>
        <div className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3" title={legacyRun ? t("dashNotRecorded") : undefined}>
          <dt className="eyebrow">{t("dashConverted")}</dt>
          <dd className="num mt-1 text-xl font-medium tracking-[-0.04em]">{legacyRun ? "—" : formatPercent(conversionRate, 0)}</dd>
        </div>
        <div className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3">
          <dt className="eyebrow flex items-center gap-1.5">
            <span className={inStore > 0 ? "size-1.5 animate-pulse-ring rounded-full bg-volt" : "size-1.5 rounded-full bg-muted-foreground/40"} aria-hidden />
            {t("dashInStore")}
          </dt>
          <dd className="num mt-1 text-xl font-medium tracking-[-0.04em]">{inStore}</dd>
        </div>
      </dl>
    </div>
  );
}
