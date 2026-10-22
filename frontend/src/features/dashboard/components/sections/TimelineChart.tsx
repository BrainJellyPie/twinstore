import { useRef, useMemo, useCallback } from "react";
import { BarChart, Bar, XAxis, ReferenceArea, ReferenceLine } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/shared/components/ui/chart";
import type { CustomerResult } from "@/shared/types/domain";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { usePlaybackControlStore } from "@/stores/playbackControlStore";
import { parseTimeToSeconds } from "@/features/playback/utils/playback";
import { useI18n } from "@/shared/i18n/i18n";

interface Props {
  customers: CustomerResult[] | null;
  minTime: number;
  maxTime: number;
}

const MARGIN = { top: 4, right: 4, bottom: 0, left: 4 };
const PADDING = { left: 8, right: 8 };

export function TimelineChart({ customers, minTime, maxTime }: Props) {
  const { t } = useI18n();
  const chartConfig = {
    visitors: { label: t("dashVisitors"), color: "var(--color-chart-1)" },
  } satisfies ChartConfig;
  const currentMinute = useSimulationMetricsStore((s) => s.currentMinute);
  const currentDay = usePlaybackControlStore((s) => s.currentDay);
  const containerRef = useRef<HTMLDivElement>(null);

  const scheduleFirstHour = Math.floor(minTime / 3600);
  const scheduleLastHour = Math.ceil(maxTime / 3600);

  const { data, firstHour, lastHour } = useMemo(() => {
    const hourCounts = new Map<number, number>();
    let dataMinHour = scheduleFirstHour;
    let dataMaxHour = scheduleLastHour;

    if (customers) {
      for (const c of customers) {
        if (c.day !== currentDay) continue;
        const arrivalHour = Math.floor(parseTimeToSeconds(c.arrival_time) / 3600);
        hourCounts.set(arrivalHour, (hourCounts.get(arrivalHour) ?? 0) + 1);
        if (arrivalHour < dataMinHour) dataMinHour = arrivalHour;
        if (arrivalHour + 1 > dataMaxHour) dataMaxHour = arrivalHour + 1;
      }
    }

    const result: { hour: number; visitors: number }[] = [];
    for (let h = dataMinHour; h < dataMaxHour; h++) {
      result.push({ hour: h + 0.5, visitors: hourCounts.get(h) ?? 0 });
    }
    return { data: result, firstHour: dataMinHour, lastHour: dataMaxHour };
  }, [customers, currentDay, scheduleFirstHour, scheduleLastHour]);

  const handleChartClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const el = containerRef.current;
    if (!el || lastHour <= firstHour) return;

    const rect = el.getBoundingClientRect();
    const plotLeft = MARGIN.left + PADDING.left;
    const plotRight = rect.width - MARGIN.right - PADDING.right;
    const plotWidth = plotRight - plotLeft;
    if (plotWidth <= 0) return;

    const relX = e.clientX - rect.left - plotLeft;
    const ratio = Math.max(0, Math.min(1, relX / plotWidth));
    const targetHour = firstHour + ratio * (lastHour - firstHour);
    const targetSec = targetHour * 3600;

    usePlaybackControlStore.getState().seek(targetSec);
  }, [firstHour, lastHour]);

  if (data.length === 0) {
    return (
      <div className="border-t px-3 py-3">
        <div className="section-title mb-2">{t("dashTimeline")}</div>
        <div className="flex h-20 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
          {t("dashNoData")}
        </div>
      </div>
    );
  }

  const currentHour = currentMinute / 3600;
  const clampedHour = Math.min(Math.max(currentHour, firstHour), lastHour);
  const started = currentHour >= firstHour;

  return (
    <div className="border-t px-3 py-3">
      <div className="section-title mb-1">{t("dashTimeline")}</div>
      <div ref={containerRef} onClick={handleChartClick} className="cursor-pointer">
        <ChartContainer config={chartConfig} className="aspect-auto h-[96px] w-full">
          <BarChart data={data} margin={MARGIN}>
            <XAxis
              dataKey="hour"
              type="number"
              domain={[firstHour, lastHour]}
              ticks={Array.from({ length: lastHour - firstHour + 1 }, (_, i) => firstHour + i)}
              tickFormatter={(h) => String(h)}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              padding={PADDING}
            />
            <ChartTooltip
              content={<ChartTooltipContent labelFormatter={(_v, payload) => {
                const hour = payload?.[0]?.payload?.hour;
                return typeof hour === "number" ? `${Math.floor(hour)}:00` : "";
              }} />}
              cursor={false}
            />
            {started && (
              <ReferenceArea
                x1={firstHour}
                x2={clampedHour}
                fill="var(--color-chart-1)"
                fillOpacity={0.08}
                ifOverflow="hidden"
              />
            )}
            {started && currentHour < lastHour && (
              <ReferenceLine
                x={clampedHour}
                stroke="var(--heat-3)"
                strokeWidth={2}
                ifOverflow="hidden"
              />
            )}
            <Bar
              dataKey="visitors"
              fill="var(--color-chart-1)"
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
            />
          </BarChart>
        </ChartContainer>
      </div>
    </div>
  );
}
