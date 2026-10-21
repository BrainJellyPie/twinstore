import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { formatMoney, formatPercent } from "@/shared/utils/money";

// Live totals up to the current playback time.
export function Summary() {
  const revenue = useSimulationMetricsStore((s) => s.revenue);
  const impulseRevenue = useSimulationMetricsStore((s) => s.impulseRevenue);
  const paidCount = useSimulationMetricsStore((s) => s.paidCount);
  const currency = useSimulationStore((s) => s.currency);
  const aov = paidCount > 0 ? revenue / paidCount : 0;
  const impulseShare = revenue > 0 ? impulseRevenue / revenue : 0;

  return (
    <div className="px-3 py-3">
      <div className="ring-aurora relative overflow-hidden rounded-2xl bg-foreground/[0.03] p-4">
        <div className="pointer-events-none absolute -top-10 -right-8 size-32 rounded-full bg-heat-2/20 blur-2xl" aria-hidden />
        <div className="eyebrow">Revenue so far</div>
        <div className="num mt-1 text-[2.4rem] leading-none font-medium tracking-[-0.06em]">{formatMoney(revenue, currency)}</div>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3">
          <div className="eyebrow">Avg. basket</div>
          <div className="num mt-1 text-xl font-medium tracking-[-0.04em]">{formatMoney(aov, currency)}</div>
        </div>
        <div className="rounded-2xl border border-glass-border bg-foreground/[0.02] p-3" title="Revenue from unplanned purchases">
          <div className="eyebrow">Impulse share</div>
          <div className="num mt-1 text-xl font-medium tracking-[-0.04em]">{formatPercent(impulseShare, 0)}</div>
        </div>
      </div>
    </div>
  );
}
