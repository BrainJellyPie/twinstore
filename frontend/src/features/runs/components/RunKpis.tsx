import type { ReactNode } from "react";
import { useState } from "react";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import type { RunSummary } from "@/shared/api/client";
import { currencyCode, formatMoney, formatPercent } from "@/shared/utils/money";

function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-md border bg-background px-2.5 py-2" title={hint}>
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums">{value}</div>
    </div>
  );
}

// Final KPIs of the run (from the backend summary), independent of playback position.
export function RunKpis({ summary }: { summary: RunSummary }) {
  const code = currencyCode(summary.currency);
  if (summary.conversion_rate === undefined) {
    return (
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        This run was made by an older version — re-run it to see conversion, basket and impulse KPIs.
      </div>
    );
  }
  return (
    <div className="border-t px-3 py-3">
      <div className="mb-2 text-xs font-medium">Run results</div>
      <div className="grid grid-cols-2 gap-2">
        <Tile label="Conversion" value={formatPercent(summary.conversion_rate)} hint="Visitors who bought at least one item" />
        <Tile label="Revenue / visitor" value={formatMoney(summary.revenue_per_visitor ?? 0, code)} />
        <Tile label="Basket value" value={formatMoney(summary.avg_basket_value ?? 0, code)} hint="Revenue per paying customer" />
        <Tile label="Units / buyer" value={(summary.avg_units_per_buyer ?? 0).toFixed(2)} />
        <Tile label="Impulse share" value={formatPercent(summary.impulse_revenue_share ?? 0)} hint="Revenue from unplanned purchases" />
        <Tile label="Avg. visit" value={`${Math.round(summary.avg_visit_sec ?? 0)}s`} hint={`${(summary.avg_path_tiles ?? 0).toFixed(1)} tiles walked on average`} />
      </div>
      <SegmentBreakdown summary={summary} />
    </div>
  );
}

const DIMENSIONS: { value: string; label: string }[] = [
  { value: "age_group", label: "Age" },
  { value: "gender", label: "Gender" },
  { value: "purpose", label: "Purpose" },
];

function SegmentBreakdown({ summary }: { summary: RunSummary }) {
  const [dimension, setDimension] = useState("age_group");
  const code = currencyCode(summary.currency);
  const rows = Object.entries(summary.segments?.[dimension] ?? {})
    .sort((a, b) => b[1].visitors - a[1].visitors)
    .slice(0, 8);
  if (rows.length === 0) return null;
  const maxRpv = Math.max(...rows.map(([, s]) => s.revenue_per_visitor), 1);

  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-[11px] font-medium text-muted-foreground">By segment</div>
        <ToggleGroup type="single" value={dimension} onValueChange={(v) => v && setDimension(v)} variant="outline" size="sm">
          {DIMENSIONS.map((d) => (
            <ToggleGroupItem key={d.value} value={d.value} className="h-6 px-2 text-[11px]">
              {d.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      <ul className="flex flex-col gap-1.5">
        {rows.map(([name, s]) => (
          <li key={name} className="text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate">{name}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {s.visitors} · {formatPercent(s.conversion_rate, 0)} conv · {formatMoney(s.revenue_per_visitor, code)}/visitor
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
              <div className="h-full rounded-full bg-chart-3" style={{ width: `${(s.revenue_per_visitor / maxRpv) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
