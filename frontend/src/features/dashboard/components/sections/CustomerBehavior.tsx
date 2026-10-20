import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";

export function CustomerBehavior() {
  const entered = useSimulationMetricsStore((s) => s.entered);
  const inStore = useSimulationMetricsStore((s) => s.inStore);
  const paidCount = useSimulationMetricsStore((s) => s.paidCount);
  const conversionRate = entered > 0 ? Math.round((paidCount / entered) * 100) : 0;

  return (
    <div className="border-t px-3 py-3">
      <div className="section-title mb-2">Customer behavior</div>
      <dl className="flex flex-col gap-1.5 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Total visitors</dt>
          <dd className="tabular-nums">{entered}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">Conversion rate</dt>
          <dd className="tabular-nums">{conversionRate}%</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">In store now</dt>
          <dd className="tabular-nums">{inStore}</dd>
        </div>
      </dl>
    </div>
  );
}
