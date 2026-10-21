import { useEffect, useState } from "react";
import { Play, Pause, SkipForward, RotateCcw, ChevronDown, ChevronLeft, ChevronRight, Layers, BarChart3, Box, Eye } from "lucide-react";
import { cn } from "@/shared/utils/cn";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { usePlaybackControlStore, type PlaybackSpeed } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore, type GraphicsMode, type HeatmapMode } from "@/stores/simulationStore";
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
  1: "Real time",
  60: "Normal",
  600: "Fast",
  3600: "Very fast",
};
const SPEED_VALUES: PlaybackSpeed[] = [1, 60, 600, 3600];

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

function formatClock12h(sec: number): string {
  const h = Math.floor(sec / 3600) % 24;
  const m = Math.floor((sec % 3600) / 60);
  const ampm = h < 12 ? "am" : "pm";
  const hh = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${hh}:${String(m).padStart(2, "0")} ${ampm}`;
}

export function TimeBar({ minTime, maxTime, hasDwell = false, hasRackStats = false }: Props) {
  const [smallScreen, setSmallScreen] = useState(() => window.matchMedia("(max-width: 1023px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 1023px)");
    const onChange = () => setSmallScreen(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
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
  const graphicsMode = useSimulationStore((s) => s.graphicsMode);
  const setGraphicsMode = useSimulationStore((s) => s.setGraphicsMode);
  const shopperView = useSimulationStore((s) => s.shopperView);
  const setShopperView = useSimulationStore((s) => s.setShopperView);

  const disabled = maxTime <= minTime;
  const dayIdx = availableDays.indexOf(currentDay);
  const isFirst = dayIdx <= 0;
  const isLast = dayIdx >= availableDays.length - 1;
  const weekdayLabel = WEEKDAYS[(currentDay - 1) % 7];

  const handleReset = () => {
    usePlaybackControlStore.getState().setDay(availableDays[0] ?? 1);
    seek(minTime);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.code !== "Space" || disabled || finished || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(el.tagName))) return;
      e.preventDefault();
      if (e.repeat) return;
      togglePlay();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [disabled, finished, togglePlay]);

  const progress = disabled ? 0 : finished ? 1 : Math.min(1, Math.max(0, (currentMinute - minTime) / (maxTime - minTime)));
  // Keep phones and the shopper's-eye view clear unless the controls are reopened.
  const [pref, setPref] = useState<{ view: boolean; collapsed: boolean } | null>(null);
  const collapsed = pref && pref.view === shopperView ? pref.collapsed : shopperView || smallScreen;

  return (
    <div role="region" aria-label="Playback controls" className={cn("glass absolute top-16 right-4 z-20 max-h-[calc(100%-12rem)] max-w-[calc(100%-2rem)] overflow-y-auto rounded-[1.4rem] text-foreground transition-[width] duration-300 xl:top-4 xl:max-h-[calc(100%-9rem)]", collapsed ? "w-[21rem]" : "w-[25rem]")}>
      <div className="flex items-center justify-between gap-2 px-3 pt-3 sm:gap-3 sm:px-5 sm:pt-4">
        <div className="min-w-0">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-xs" className="-ml-1.5 rounded-full" disabled={isFirst} onClick={prevDay} aria-label="Previous day">
              <ChevronLeft />
            </Button>
            <span className="eyebrow">
              Day {dayIdx + 1} · {weekdayLabel}
            </span>
            <Button variant="ghost" size="icon-xs" className="rounded-full" disabled={isLast} onClick={nextDay} aria-label="Next day">
              <ChevronRight />
            </Button>
          </div>
          <div className={cn("num mt-1 whitespace-nowrap leading-none font-medium tracking-[-0.06em] transition-[font-size]", collapsed ? "text-[1.5rem] sm:text-[2rem]" : "text-[1.75rem] sm:text-[2.6rem]")}>
            {finished ? "Closed" : formatClock12h(currentMinute)}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {finished ? (
            <Button variant="outline" className="h-11 gap-1.5 rounded-full px-4" onClick={handleReset}>
              <RotateCcw className="size-4" />
              Replay
            </Button>
          ) : (
            <>
              <Button
                variant="outline"
                size="icon-lg"
                className="size-8 rounded-full sm:size-10"
                disabled={disabled}
                onClick={() => seek(maxTime)}
                title="Skip to closing time"
                aria-label="Skip to closing time"
              >
                <SkipForward className="size-4" />
              </Button>
              <button
                type="button"
                disabled={disabled}
                onClick={togglePlay}
                title={playing ? "Pause (Space)" : "Play (Space)"}
                aria-label={playing ? "Pause" : "Play"}
                className={cn(
                  "grid size-10 place-items-center rounded-full bg-primary text-primary-foreground transition-[transform,box-shadow] duration-200 hover:scale-105 active:scale-95 disabled:opacity-40 sm:size-14",
                  "shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_0_0_6px_color-mix(in_oklab,var(--primary)_14%,transparent),0_14px_36px_-10px_var(--primary)]",
                  !playing && !disabled && "animate-pulse-ring",
                )}
              >
                {playing ? <Pause className="size-5" fill="currentColor" /> : <Play className="ml-0.5 size-5" fill="currentColor" />}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="px-3 pt-3 pb-1 sm:px-5 sm:pt-4">
        <input
          type="range"
          min={minTime}
          max={maxTime}
          step={60}
          value={finished ? maxTime : Math.min(Math.max(currentMinute, minTime), maxTime)}
          disabled={disabled}
          onChange={(e) => seek(Number(e.target.value))}
          className="w-full"
          style={{ background: "transparent" }}
          aria-label="Scrub through the day"
        />
        <div className="num -mt-0.5 flex justify-between text-[0.68rem] text-muted-foreground">
          <span>{formatClock12h(minTime)}</span>
          <button
            type="button"
            onClick={() => setPref({ view: shopperView, collapsed: !collapsed })}
            className="flex items-center gap-1 rounded-full px-2 text-muted-foreground transition-colors hover:text-foreground"
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand playback controls" : "Collapse playback controls"}
          >
            {Math.round(progress * 100)}% · {collapsed ? "controls" : "less"}
            <ChevronDown className={cn("size-3 transition-transform", !collapsed && "rotate-180")} />
          </button>
          <span>{formatClock12h(maxTime)}</span>
        </div>
      </div>

      {collapsed ? (
        shopperView && (
          <div className="flex items-center justify-between border-t border-glass-border px-5 py-2.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><Eye className="size-3.5" /> Shopper's-eye view</span>
            <button type="button" onClick={() => setShopperView(false)} className="rounded-full px-2 py-0.5 font-medium text-foreground hover:bg-foreground/[0.06]">
              Exit
            </button>
          </div>
        )
      ) : (
      <div className="mt-2 space-y-3 border-t border-glass-border bg-foreground/[0.02] px-3 py-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow w-14">Speed</span>
          <ToggleGroup
            type="single"
            aria-label="Playback speed"
            value={String(speed)}
            onValueChange={(v) => v && setSpeed(Number(v) as PlaybackSpeed)}
            size="sm"
            disabled={disabled}
            className="grid min-w-40 flex-1 grid-cols-2 rounded-xl bg-foreground/[0.05] p-0.5 sm:flex"
          >
            {SPEED_VALUES.map((s) => (
              <ToggleGroupItem key={s} value={String(s)} title={s === 1 ? "1 second of simulation per second" : `${s} seconds of simulation per second`} className="h-7 flex-1 rounded-[0.6rem] text-[0.8rem]">
                {SPEED_LABEL[s]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow flex w-14 items-center gap-1">
            <Layers className="size-3" aria-hidden />
            Layer
          </span>
          <ToggleGroup
            type="single"
            value={heatmapMode}
            onValueChange={(v) => v && setHeatmapMode(v as HeatmapMode)}
            size="sm"
            aria-label="Heatmap layer"
            className="min-w-40 flex-1 flex-wrap rounded-xl bg-foreground/[0.05] p-0.5"
          >
            {HEATMAP_LAYERS.map((l) => (
              <ToggleGroupItem
                key={l.value}
                value={l.value}
                title={l.hint}
                disabled={l.value === "dwell" && !hasDwell}
                className="h-7 flex-1 rounded-[0.6rem] text-[0.8rem]"
              >
                {l.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        {heatmapMode !== "off" && (
          <div className="flex items-center gap-2 pl-[4.25rem] text-[0.72rem] text-muted-foreground">
            low
            <span className="h-1.5 flex-1 rounded-full" style={{ background: paletteGradient(heatmapMode) }} />
            high
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow flex w-14 items-center gap-1">
            <Box className="size-3" aria-hidden />
            View
          </span>
          <ToggleGroup
            type="single"
            value={graphicsMode}
            onValueChange={(v) => v && setGraphicsMode(v as GraphicsMode)}
            size="sm"
            aria-label="Graphics"
            className="rounded-xl bg-foreground/[0.05] p-0.5"
          >
            <ToggleGroupItem value="classic" className="h-7 rounded-[0.6rem] px-2.5 text-[0.8rem]" title="Low-poly look">
              Classic
            </ToggleGroupItem>
            <ToggleGroupItem value="realistic" className="h-7 rounded-[0.6rem] px-2.5 text-[0.8rem]" title="Lit store interior with stocked shelves">
              Realistic
            </ToggleGroupItem>
          </ToggleGroup>
          <div className="ml-auto flex items-center gap-1">
            <Button
              variant={shopperView ? "default" : "ghost"}
              size="icon-sm"
              onClick={() => setShopperView(!shopperView)}
              title="Shopper view — first person, from a shopper's eyes"
              aria-label="Shopper view"
              aria-pressed={shopperView}
            >
              <Eye />
            </Button>
            <Button
              variant={rackOverlayOn ? "default" : "ghost"}
              size="icon-sm"
              onClick={toggleRackOverlay}
              disabled={!hasRackStats}
              title={hasRackStats ? "Rack KPIs — revenue and stop→buy rate per rack" : "Re-run to get rack KPIs"}
              aria-label="Rack KPIs"
              aria-pressed={rackOverlayOn}
            >
              <BarChart3 />
            </Button>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
