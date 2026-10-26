import { useState } from "react";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import type { Store } from "@/shared/types/domain";
import { formatMoney } from "@/shared/utils/money";
import { useSimulationStore } from "@/stores/simulationStore";
import { useI18n } from "@/shared/i18n/i18n";

type SortKey = "revenue" | "visitors";
const SHOW_LIMIT = 10;
const EXCLUDED_TYPES = new Set(["entrance", "exit", "counter"]);

interface Props {
  store: Store;
}

export function RackRanking({ store }: Props) {
  const { t } = useI18n();
  const rackMetrics = useSimulationMetricsStore((s) => s.rackMetrics);
  const entered = useSimulationMetricsStore((s) => s.entered);
  const finished = useSimulationMetricsStore((s) => s.finished);
  const [sortBy, setSortBy] = useState<SortKey>("revenue");
  const currency = useSimulationStore((s) => s.currency);

  const rackMap = new Map(
    store.racks.map((r) => [r.id, r]),
  );

  const filtered = rackMetrics.filter((m) => {
    const rack = rackMap.get(m.rackId);
    return rack && !EXCLUDED_TYPES.has(rack.type);
  });

  const sorted = [...filtered].sort((a, b) =>
    sortBy === "revenue" ? b.revenue - a.revenue : b.visitors - a.visitors,
  );
  const shown = sorted.slice(0, SHOW_LIMIT);
  const totalCount = sorted.length;

  const totalRevenue = filtered.reduce((sum, m) => sum + m.revenue, 0);
  const totalVisitors = entered;

  return (
    <div className="border-t px-3 py-3">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="section-title">{t("dashRacks")}</div>
        <ToggleGroup
          type="single"
          value={sortBy}
          onValueChange={(v) => v && setSortBy(v as SortKey)}
          variant="outline"
          size="sm"
        >
          <ToggleGroupItem
            value="revenue"
            className="h-6 px-2 text-[0.72rem] data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
          >
            {t("dashByRevenue")}
          </ToggleGroupItem>
          <ToggleGroupItem
            value="visitors"
            className="h-6 px-2 text-[0.72rem] data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
          >
            {t("dashByVisitors")}
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {shown.length === 0 ? (
        <div className="py-3 text-center text-xs text-muted-foreground">
          {finished ? t("dashNoRackSales") : t("dashRacksFillIn")}
        </div>
      ) : (
        <>
          <ol className="flex flex-col gap-2.5">
            {shown.map((m) => {
              const rack = rackMap.get(m.rackId);
              const name = rack?.rack_name ?? m.rackId;
              const value = sortBy === "revenue" ? m.revenue : m.visitors;
              const total = sortBy === "revenue" ? totalRevenue : totalVisitors;
              const ratio = total > 0 ? value / total : 0;

              return (
                <li key={m.rackId}>
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate" title={name}>{name}</span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {sortBy === "revenue"
                        ? formatMoney(m.revenue, currency)
                        : t("dashVisitorCount", { count: m.visitors })}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-chart-2"
                      style={{ width: `${Math.min(ratio * 100, 100)}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ol>
          {totalCount > SHOW_LIMIT && (
            <div className="mt-2 text-xs text-muted-foreground">
              {t("dashMoreCount", { count: totalCount - SHOW_LIMIT })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
