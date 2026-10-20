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
    <div className="border-t px-3 py-3">
      <div className="mb-2 text-xs font-medium">Summary</div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <div className="text-[11px] text-muted-foreground">Total revenue</div>
          <div className="mt-0.5 text-lg font-bold tabular-nums">{formatMoney(revenue, currency)}</div>
        </div>
        <div>
          <div className="text-[11px] text-muted-foreground">Avg. order value</div>
          <div className="mt-0.5 text-lg font-bold tabular-nums">{formatMoney(aov, currency)}</div>
        </div>
        <div>
          <div className="text-[11px] text-muted-foreground" title="Revenue from unplanned purchases">Impulse share</div>
          <div className="mt-0.5 text-lg font-bold tabular-nums">{formatPercent(impulseShare, 0)}</div>
        </div>
      </div>
    </div>
  );
}
