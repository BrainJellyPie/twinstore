import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useI18n } from "@/shared/i18n/i18n";

interface Props {
  minTime: number;
  maxTime: number;
}

// How far through the simulated day playback is, as a heat-colored progress line.
export function PlaybackStatus({ minTime, maxTime }: Props) {
  const { t } = useI18n();
  const currentMinute = useSimulationMetricsStore((s) => s.currentMinute);
  const finished = useSimulationMetricsStore((s) => s.finished);
  const hasRange = maxTime > minTime;
  const pct = !hasRange ? 0 : finished ? 100 : Math.max(0, Math.min(100, ((currentMinute - minTime) / (maxTime - minTime)) * 100));

  const label = !hasRange ? t("dashNoRunData") : finished ? t("dashDayComplete") : pct <= 0 ? t("dashPressPlay") : t("dashPlaying", { percent: Math.round(pct) });

  return (
    <div className="px-3 pt-1 pb-3">
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className={finished ? "font-medium text-foreground" : "text-muted-foreground"}>{label}</span>
        <span className="num text-xs text-muted-foreground">{Math.round(pct)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-foreground/10" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
        <div className="heat-gradient h-full rounded-full transition-[width] duration-300" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
