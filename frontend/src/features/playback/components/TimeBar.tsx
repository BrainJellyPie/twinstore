import { Play, Pause, SkipForward, RotateCcw, ChevronLeft, ChevronRight, Layers, BarChart3 } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { usePlaybackControlStore, type PlaybackSpeed } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore, type HeatmapMode } from "@/stores/simulationStore";
import { paletteGradient } from "@/features/store-viewer/utils/heatmapPalette";

interface Props {
  minTime: number;
  maxTime: number;
  // Runs made before v0.2 have no dwell-time layer / rack KPIs.
  hasDwell?: boolean;
  hasRackStats?: boolean;
}

const HEATMAP_LAYERS: { value: HeatmapMode; label: string; hint: string }[] = [
  { value: "off", label: "Off", hint: "No heatmap" },
  { value: "footfall", label: "Footfall", hint: "Where shoppers walked and stopped (event count per tile)" },
  { value: "dwell", label: "Dwell", hint: "Seconds spent per tile — where attention actually went" },
  { value: "traffic", label: "Traffic", hint: "Predicted shortest-path load between racks (layout only)" },
];

const SPEED_LABEL: Record<PlaybackSpeed, string> = {
  60: "Normal",
  600: "Fast",
  3600: "Very fast",
};
const SPEED_VALUES: PlaybackSpeed[] = [60, 600, 3600];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

function formatClock12h(sec: number): string {
  const h = Math.floor(sec / 3600) % 24;
  const m = Math.floor((sec % 3600) / 60);
  const ampm = h < 12 ? "am" : "pm";
  const hh = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${hh}:${String(m).padStart(2, "0")} ${ampm}`;
}

export function TimeBar({ minTime, maxTime, hasDwell = false, hasRackStats = false }: Props) {
  const playing = usePlaybackControlStore((s) => s.playing);
  const speed = usePlaybackControlStore((s) => s.speed);
  const togglePlay = usePlaybackControlStore((s) => s.togglePlay);
  const setSpeed = usePlaybackControlStore((s) => s.setSpeed);
  const seek = usePlaybackControlStore((s) => s.seek);
  const currentDay = usePlaybackControlStore((s) => s.currentDay);
  const availableDays = usePlaybackControlStore((s) => s.availableDays);
  const nextDay = usePlaybackControlStore((s) => s.nextDay);
  const prevDay = usePlaybackControlStore((s) => s.prevDay);
  const currentMinute = useSimulationMetricsStore((s) => s.currentMinute);
  const finished = useSimulationMetricsStore((s) => s.finished);
  const heatmapMode = useSimulationStore((s) => s.heatmapMode);
  const setHeatmapMode = useSimulationStore((s) => s.setHeatmapMode);
  const rackOverlayOn = useSimulationStore((s) => s.rackOverlayOn);
  const toggleRackOverlay = useSimulationStore((s) => s.toggleRackOverlay);

  const disabled = maxTime <= minTime;
  const dayIdx = availableDays.indexOf(currentDay);
  const isFirst = dayIdx <= 0;
  const isLast = dayIdx >= availableDays.length - 1;
  const weekdayLabel = WEEKDAYS[(currentDay - 1) % 7];

  const handleReset = () => {
    usePlaybackControlStore.getState().setDay(availableDays[0] ?? 1);
    seek(minTime);
  };

  return (
    <div className="absolute top-4 right-4 w-[380px] rounded-lg border bg-background/95 p-4 shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="size-5 p-0"
              disabled={isFirst}
              onClick={prevDay}
            >
              <ChevronLeft className="size-3" />
            </Button>
            <span className="text-xs font-medium text-muted-foreground">
              Day {dayIdx + 1} ({weekdayLabel})
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="size-5 p-0"
              disabled={isLast}
              onClick={nextDay}
            >
              <ChevronRight className="size-3" />
            </Button>
          </div>
          <div className="font-mono text-3xl font-bold tabular-nums leading-none">
            {finished ? "End" : formatClock12h(currentMinute)}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {finished ? (
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1 text-xs"
              onClick={handleReset}
            >
              <RotateCcw className="size-3" />
              Reset
            </Button>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1 text-xs"
                disabled={disabled}
                onClick={() => seek(maxTime)}
              >
                <SkipForward className="size-3" />
                Skip
              </Button>
              <Button
                size="sm"
                className="h-8 gap-1 px-3 text-xs"
                disabled={disabled}
                onClick={togglePlay}
              >
                {playing ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
                {playing ? "Pause" : "Play"}
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-muted-foreground">Speed</span>
          <ToggleGroup
            type="single"
            value={String(speed)}
            onValueChange={(v) => v && setSpeed(Number(v) as PlaybackSpeed)}
            variant="outline"
            size="sm"
            disabled={disabled}
          >
            {SPEED_VALUES.map((s) => (
              <ToggleGroupItem
                key={s}
                value={String(s)}
                className="h-7 px-2.5 text-xs"
              >
                {SPEED_LABEL[s]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <Button
          variant={rackOverlayOn ? "default" : "outline"}
          size="sm"
          className="h-7 gap-1 px-2 text-xs"
          onClick={toggleRackOverlay}
          disabled={!hasRackStats}
          title={hasRackStats ? "Revenue and stop→buy rate per rack" : "Re-run to get rack KPIs"}
        >
          <BarChart3 className="size-3" />
          Rack KPIs
        </Button>
      </div>
      <div className="mt-3 flex items-center gap-2 border-t pt-3">
        <Layers className="size-3 shrink-0 text-muted-foreground" aria-hidden />
        <ToggleGroup
          type="single"
          value={heatmapMode}
          onValueChange={(v) => v && setHeatmapMode(v as HeatmapMode)}
          variant="outline"
          size="sm"
          aria-label="Heatmap layer"
        >
          {HEATMAP_LAYERS.map((l) => (
            <ToggleGroupItem
              key={l.value}
              value={l.value}
              title={l.hint}
              disabled={l.value === "dwell" && !hasDwell}
              className="h-7 px-2 text-xs"
            >
              {l.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        {heatmapMode !== "off" && (
          <div className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
            low
            <span className="h-2 w-14 rounded-full" style={{ background: paletteGradient(heatmapMode) }} />
            high
          </div>
        )}
      </div>
    </div>
  );
}
