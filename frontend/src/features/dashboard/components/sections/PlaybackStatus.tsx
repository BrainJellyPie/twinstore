import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";

interface Props {
  minTime: number;
  maxTime: number;
}

// How far through the simulated day playback is, as a heat-colored progress line.
export function PlaybackStatus({ minTime, maxTime }: Props) {
  const currentMinute = useSimulationMetricsStore((s) => s.currentMinute);
  const finished = useSimulationMetricsStore((s) => s.finished);
  const hasRange = maxTime > minTime;
  const pct = !hasRange ? 0 : finished ? 100 : Math.max(0, Math.min(100, ((currentMinute - minTime) / (maxTime - minTime)) * 100));

  const label = !hasRange ? "No data in this run" : finished ? "Day complete" : pct <= 0 ? "Press play to start the day" : `Playing — ${Math.round(pct)}% of the day`;

  return (
    <div className="px-3 pt-1 pb-3">
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className={finished ? "font-medium text-primary" : "text-muted-foreground"}>{label}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
        <div className="heat-gradient h-full rounded-full transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
