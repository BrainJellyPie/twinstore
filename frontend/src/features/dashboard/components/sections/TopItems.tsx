import { useState } from "react";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import type { Store } from "@/shared/types/domain";
import { formatMoney } from "@/shared/utils/money";
import { useSimulationStore } from "@/stores/simulationStore";
import { useI18n } from "@/shared/i18n/i18n";

type SortKey = "revenue" | "quantity";
const SHOW_LIMIT = 10;

interface Props {
  store: Store;
}

export function TopItems({ store }: Props) {
  const { t } = useI18n();
  const skuSales = useSimulationMetricsStore((s) => s.skuSales);
  const finished = useSimulationMetricsStore((s) => s.finished);
  const [sortBy, setSortBy] = useState<SortKey>("revenue");
  const currency = useSimulationStore((s) => s.currency);
  const [showAll, setShowAll] = useState(false);

  const rackNames = new Map(
    store.racks.map((r) => [r.id, r.rack_name]),
  );

  const sorted = [...skuSales];
  if (sortBy === "quantity") sorted.sort((a, b) => b.quantity - a.quantity);

  const totalCount = sorted.length;
  const shown = showAll ? sorted : sorted.slice(0, SHOW_LIMIT);

  const totalRevenue = sorted.reduce((sum, s) => sum + s.revenue, 0);
  const totalQuantity = sorted.reduce((sum, s) => sum + s.quantity, 0);

  return (
    <div className="border-t px-3 py-3">
      <div className="mb-2.5 flex items-center justify-between">
        <div className="section-title">{t("dashTopItems")}</div>
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
            value="quantity"
            className="h-6 px-2 text-[0.72rem] data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:border-primary"
          >
            {t("dashByQuantity")}
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {shown.length === 0 ? (
        <div className="py-3 text-center text-xs text-muted-foreground">
          {finished ? t("dashNoSales") : t("dashItemsFillIn")}
        </div>
      ) : (
        <>
          <ol className="flex flex-col gap-2.5">
            {shown.map((s, i) => {
              const value = sortBy === "revenue" ? s.revenue : s.quantity;
              const total = sortBy === "revenue" ? totalRevenue : totalQuantity;
              const ratio = total > 0 ? value / total : 0;
              const rackName = rackNames.get(s.rackId);

              return (
                <li key={s.sku}>
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="truncate" title={s.name}>{s.name}</span>
                      {rackName && (
                        <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[0.72rem] text-muted-foreground">
                          {rackName}
                        </span>
                      )}
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {sortBy === "revenue"
                        ? formatMoney(s.revenue, currency)
                        : t("dashSoldCount", { count: s.quantity })}
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
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="mt-2 text-xs text-muted-foreground hover:text-foreground"
            >
              {showAll ? t("showLess") : t("dashViewAll", { count: totalCount })}
            </button>
          )}
        </>
      )}
    </div>
  );
}
