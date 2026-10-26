import { useEffect, useState } from "react";
import { Play, Pause, SkipForward, RotateCcw, ChevronDown, ChevronLeft, ChevronRight, Layers, BarChart3, Box, Eye } from "lucide-react";
import { cn } from "@/shared/utils/cn";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { usePlaybackControlStore, type PlaybackSpeed } from "@/stores/playbackControlStore";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore, type GraphicsMode, type HeatmapMode } from "@/stores/simulationStore";
import { paletteGradient } from "@/features/store-viewer/utils/heatmapPalette";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { clockTime, weekdayShort } from "@/shared/i18n/timeFormat";
import { formatPercent } from "@/shared/utils/money";

interface Props {
  minTime: number;
  maxTime: number;
  // Runs made before v0.2 have no dwell-time layer / rack KPIs.
  hasDwell?: boolean;
  hasRackStats?: boolean;
}

const HEATMAP_LAYERS: { value: HeatmapMode; label: MessageKey; hint: MessageKey }[] = [
  { value: "off", label: "pbLayerOff", hint: "pbLayerOffHint" },
  { value: "footfall", label: "pbLayerFootfall", hint: "pbLayerFootfallHint" },
  { value: "dwell", label: "pbLayerDwell", hint: "pbLayerDwellHint" },
  { value: "traffic", label: "pbLayerTraffic", hint: "pbLayerTrafficHint" },
];

const SPEED_LABEL: Record<PlaybackSpeed, MessageKey> = {
  1: "pbSpeedRealTime",
  60: "pbSpeedNormal",
  600: "pbSpeedFast",
  3600: "pbSpeedVeryFast",
};
const SPEED_VALUES: PlaybackSpeed[] = [1, 60, 600, 3600];

// Phones, and laptop-height windows where the full panel would cover a large part of the store.
const FOLDED_BY_DEFAULT = "(max-width: 1023px), (max-height: 960px)";

export function TimeBar({ minTime, maxTime, hasDwell = false, hasRackStats = false }: Props) {
  const { locale, t } = useI18n();
  const [smallScreen, setSmallScreen] = useState(() => window.matchMedia(FOLDED_BY_DEFAULT).matches);
  useEffect(() => {
    const media = window.matchMedia(FOLDED_BY_DEFAULT);
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
  const weekdayLabel = weekdayShort(currentDay, locale);

  const handleReset = () => {
    usePlaybackControlStore.getState().setDay(availableDays[0] ?? 1);
    seek(minTime);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target instanceof HTMLElement ? e.target : null;
      if (disabled || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && !e.shiftKey) {
        // Controls that move with the arrows themselves (sliders, tab and toggle rows) keep them.
        if (el?.closest("input, textarea, select, button, a, [contenteditable=true], [role=slider], [role=tab], [role=radio], [role=option], [role=menuitem]")) return;
        e.preventDefault();
        const now = useSimulationMetricsStore.getState().currentMinute;  // seconds of the day, despite its name
        seek(Math.min(maxTime, Math.max(minTime, now + (e.key === "ArrowLeft" ? -900 : 900))));
        return;
      }
      if (e.code !== "Space" || finished) return;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(el.tagName))) return;
      e.preventDefault();
      if (e.repeat) return;
      togglePlay();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [disabled, finished, togglePlay, seek, minTime, maxTime]);

  const progress = disabled ? 0 : finished ? 1 : Math.min(1, Math.max(0, (currentMinute - minTime) / (maxTime - minTime)));
  // Keep phones, short windows and the shopper's-eye view clear unless the controls are reopened.
  const [pref, setPref] = useState<{ view: boolean; collapsed: boolean } | null>(null);
  const collapsed = pref && pref.view === shopperView ? pref.collapsed : shopperView || smallScreen;

  // Dense panel glass: compass labels and speech bubbles behind it must not read through.
  return (
    <div role="region" aria-label={t("pbRegion")} className={cn("panel absolute top-16 right-4 z-20 max-h-[calc(100%-12rem)] max-w-[calc(100%-2rem)] overflow-y-auto rounded-[1.4rem] text-foreground transition-[width] duration-300 xl:top-4 xl:max-h-[calc(100%-9rem)]", collapsed ? "w-[21rem]" : "w-[25rem]")}>
      <div className="flex items-center justify-between gap-2 px-3 pt-3 sm:gap-3 sm:px-5 sm:pt-4">
        <div className="min-w-0">
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-xs" className="-ml-1.5 rounded-full" disabled={isFirst} onClick={prevDay} aria-label={t("pbPreviousDay")}>
              <ChevronLeft />
            </Button>
            <span className="eyebrow">
              {t("pbDayOf", { day: dayIdx + 1, weekday: weekdayLabel })}
            </span>
            <Button variant="ghost" size="icon-xs" className="rounded-full" disabled={isLast} onClick={nextDay} aria-label={t("pbNextDay")}>
              <ChevronRight />
            </Button>
          </div>
          <div className={cn("num mt-1 whitespace-nowrap leading-none font-medium tracking-[-0.06em] transition-[font-size]", collapsed ? "text-[1.5rem] sm:text-[2rem]" : "text-[1.75rem] sm:text-[2.6rem]")}>
            {finished ? t("pbClosed") : clockTime(currentMinute, locale)}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {finished ? (
            <Button variant="outline" className="h-11 gap-1.5 rounded-full px-4" onClick={handleReset}>
              <RotateCcw className="size-4" />
              {t("pbReplay")}
            </Button>
          ) : (
            <>
              <Button
                variant="outline"
                size="icon-lg"
                className="size-8 rounded-full sm:size-10"
                disabled={disabled}
                onClick={() => seek(maxTime)}
                title={t("pbSkipToClose")}
                aria-label={t("pbSkipToClose")}
              >
                <SkipForward className="size-4" />
              </Button>
              <button
                type="button"
                data-playback-play
                disabled={disabled}
                onClick={togglePlay}
                title={playing ? t("pbPauseSpace") : t("pbPlaySpace")}
                aria-label={playing ? t("pbPause") : t("pbPlay")}
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
          aria-label={t("pbScrub")}
          // The value is seconds since midnight; screen readers hear the store clock instead.
          aria-valuetext={clockTime(finished ? maxTime : Math.min(Math.max(currentMinute, minTime), maxTime), locale)}
        />
        <div className="num -mt-0.5 flex justify-between text-[0.68rem] text-muted-foreground">
          <span>{clockTime(minTime, locale)}</span>
          <button
            type="button"
            onClick={() => setPref({ view: shopperView, collapsed: !collapsed })}
            className="flex items-center gap-1 rounded-full px-2 text-muted-foreground transition-colors hover:text-foreground"
            aria-expanded={!collapsed}
            aria-label={collapsed ? t("pbExpand") : t("pbCollapse")}
          >
            {formatPercent(progress, 0)} · {collapsed ? t("pbMore") : t("pbLess")}
            <ChevronDown className={cn("size-3 transition-transform", !collapsed && "rotate-180")} />
          </button>
          <span>{clockTime(maxTime, locale)}</span>
        </div>
      </div>

      {collapsed ? (
        shopperView && (
          <div className="flex items-center justify-between border-t border-glass-border px-5 py-2.5 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><Eye className="size-3.5" /> {t("pbShopperEye")}</span>
            <button type="button" onClick={() => setShopperView(false)} className="rounded-full px-2 py-0.5 font-medium text-foreground hover:bg-foreground/[0.06]">
              {t("pbExit")}
            </button>
          </div>
        )
      ) : (
      <div className="mt-2 space-y-3 border-t border-glass-border bg-foreground/[0.02] px-3 py-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow w-14">{t("pbSpeed")}</span>
          <ToggleGroup
            type="single"
            aria-label={t("pbPlaybackSpeed")}
            value={String(speed)}
            onValueChange={(v) => v && setSpeed(Number(v) as PlaybackSpeed)}
            size="sm"
            disabled={disabled}
            className="grid min-w-40 flex-1 grid-cols-2 rounded-xl bg-foreground/[0.05] p-0.5 sm:flex"
          >
            {SPEED_VALUES.map((s) => (
              <ToggleGroupItem key={s} value={String(s)} title={s === 1 ? t("pbSpeedHintOne") : t("pbSpeedHint", { seconds: String(s) })} className="h-7 flex-1 rounded-[0.6rem] text-[0.8rem]">
                {t(SPEED_LABEL[s])}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow flex w-14 items-center gap-1">
            <Layers className="size-3" aria-hidden />
            {t("pbLayer")}
          </span>
          <ToggleGroup
            type="single"
            value={heatmapMode}
            onValueChange={(v) => v && setHeatmapMode(v as HeatmapMode)}
            size="sm"
            aria-label={t("pbHeatmapLayer")}
            className="min-w-40 flex-1 flex-wrap rounded-xl bg-foreground/[0.05] p-0.5"
          >
            {HEATMAP_LAYERS.map((l) => (
              <ToggleGroupItem
                key={l.value}
                value={l.value}
                title={t(l.hint)}
                disabled={l.value === "dwell" && !hasDwell}
                className="h-7 flex-1 rounded-[0.6rem] text-[0.8rem]"
              >
                {t(l.label)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>
        {heatmapMode !== "off" && (
          <div className="flex items-center gap-2 pl-[4.25rem] text-[0.72rem] text-muted-foreground">
            {t("pbLow")}
            <span className="h-1.5 flex-1 rounded-full" style={{ background: paletteGradient(heatmapMode) }} />
            {t("pbHigh")}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="eyebrow flex w-14 items-center gap-1">
            <Box className="size-3" aria-hidden />
            {t("pbView")}
          </span>
          <ToggleGroup
            type="single"
            value={graphicsMode}
            onValueChange={(v) => v && setGraphicsMode(v as GraphicsMode)}
            size="sm"
            aria-label={t("pbGraphics")}
            className="rounded-xl bg-foreground/[0.05] p-0.5"
          >
            <ToggleGroupItem value="classic" className="h-7 rounded-[0.6rem] px-2.5 text-[0.8rem]" title={t("pbClassicHint")}>
              {t("pbClassic")}
            </ToggleGroupItem>
            <ToggleGroupItem value="realistic" className="h-7 rounded-[0.6rem] px-2.5 text-[0.8rem]" title={t("pbRealisticHint")}>
              {t("pbRealistic")}
            </ToggleGroupItem>
          </ToggleGroup>
          <div className="ml-auto flex items-center gap-1">
            <Button
              variant={shopperView ? "default" : "ghost"}
              size="icon-sm"
              onClick={() => setShopperView(!shopperView)}
              title={t("pbShopperViewHint")}
              aria-label={t("pbShopperView")}
              aria-pressed={shopperView}
            >
              <Eye />
            </Button>
            <Button
              variant={rackOverlayOn ? "default" : "ghost"}
              size="icon-sm"
              onClick={toggleRackOverlay}
              disabled={!hasRackStats}
              title={hasRackStats ? t("pbRackKpisHint") : t("pbRackKpisRerun")}
              aria-label={t("pbRackKpis")}
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
