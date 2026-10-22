import { useMemo, useState } from "react";
import type { Store, Persona } from "@/shared/types/domain";
import type { RunSummary } from "@/shared/api/client";
import { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/shared/components/ui/sheet";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { LayoutExcelControls } from "@/features/layouts/components/LayoutExcelControls";
import { RackDetailView } from "./RackDetailView";
import { currencyCode } from "@/shared/utils/money";
import { LayoutEditInWords } from "./LayoutEditInWords";
import { formatWeeklyHours } from "@/features/layouts/weeklyHours";

type CustomerTab = "identity" | "purpose" | "age" | "gender";
const CUSTOMER_TABS: { value: CustomerTab; label: string }[] = [
  { value: "identity", label: "Persona" },
  { value: "purpose", label: "Purpose" },
  { value: "age", label: "Age group" },
  { value: "gender", label: "Gender" },
];

// Category-marker dots — 10 well-separated hues from Tailwind's default 500 palette,
// theme-independent for stable visual differentiation.
const DOT_COLORS = [
  "#3b82f6", // blue-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#f43f5e", // rose-500
  "#8b5cf6", // violet-500
  "#06b6d4", // cyan-500
  "#f97316", // orange-500
  "#d946ef", // fuchsia-500
  "#84cc16", // lime-500
  "#6366f1", // indigo-500
];

interface Props {
  // null is allowed so the Settings tab still renders (as a placeholder) in the
  // empty-floor state — see early return below.
  store: Store | null;
  summary: RunSummary | null;
  personas: Persona[];
  location: string;
  // In playback mode both ids are undefined → editableLayout is forced false.
  projectId?: string;
  setupId?: string;
  editableLayout?: boolean;
}

// In ready/running there is no summary yet — compute the distribution from personas.
// In playback we prefer the actual-visitor counts (summary).
function breakdownFromPersonas(personas: Persona[]): Pick<
  RunSummary,
  "by_identity" | "by_purpose" | "by_age" | "by_gender"
> {
  const by_identity: Record<string, number> = {};
  const by_purpose: Record<string, number> = {};
  const by_age: Record<string, number> = {};
  const by_gender: Record<string, number> = {};
  for (const p of personas) {
    by_identity[p.identity] = (by_identity[p.identity] ?? 0) + 1;
    by_purpose[p.purpose] = (by_purpose[p.purpose] ?? 0) + 1;
    by_age[p.age_group] = (by_age[p.age_group] ?? 0) + 1;
    by_gender[p.gender] = (by_gender[p.gender] ?? 0) + 1;
  }
  return { by_identity, by_purpose, by_age, by_gender };
}

export function SettingsPanel({ store, summary, personas, location, projectId, setupId, editableLayout }: Props) {
  const [tab, setTab] = useState<CustomerTab>("identity");

  // useMemo must precede any early return to preserve hook order.
  const breakdown = useMemo(
    () => summary ?? breakdownFromPersonas(personas),
    [summary, personas],
  );

  // Empty-floor entry: render only a placeholder; skip all store-dependent sections
  // (rack/item counts, Excel controls, RackDetailView).
  if (store == null) {
    return (
      <div className="px-3 pt-3 text-xs text-muted-foreground">
        Add a floor first to see store info.
      </div>
    );
  }

  const rackCount = store.racks.filter((r) => r.type !== "entrance" && r.type !== "exit").length;
  const itemCount = store.racks.reduce(
    (sum, r) => sum + r.slots.reduce((n, s) => n + (s.items?.length ?? 0), 0),
    0,
  );

  const tabData: Record<string, number> = (() => {
    switch (tab) {
      case "identity": return breakdown.by_identity;
      case "purpose": return breakdown.by_purpose;
      case "age": return breakdown.by_age;
      case "gender": return breakdown.by_gender;
    }
  })();

  const sortedEntries = Object.entries(tabData).sort(([, a], [, b]) => b - a);
  const total = sortedEntries.reduce((sum, [, v]) => sum + v, 0);
  // Customers are written per open day, so the total spans the week, not one day.
  const days = new Set(personas.map((p) => p.day)).size;
  const infoRows: [string, string][] = [
    ["Store name", store.name || "—"],
    ["Address", location || "—"],
    ["Store type", store.type || "—"],
    ["Price currency", currencyCode(summary?.currency ?? store.currency ?? undefined)],
    ["Opening hours", formatWeeklyHours(store.weekly_schedule ?? [])],
  ];

  return (
    <Sheet>
      <div className="flex flex-col gap-3 py-3">
        <section className="rounded-md border px-3 py-3">
          <h3 className="mb-2 text-xs font-semibold">Store info</h3>
          <dl className="flex flex-col gap-1.5">
            {infoRows.map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-3">
                <dt className="shrink-0 text-xs text-muted-foreground">{label}</dt>
                <dd className="min-w-0 text-right text-xs break-words">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="rounded-md border px-3 py-3">
          <h3 className="mb-2 text-xs font-semibold">Synthetic Customers</h3>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={tab}
            onValueChange={(v) => {
              if (v) setTab(v as CustomerTab);
            }}
            className="mb-3"
            aria-label="Customer distribution metric"
          >
            {CUSTOMER_TABS.map((t) => (
              <ToggleGroupItem
                key={t.value}
                value={t.value}
                className="text-xs"
              >
                {t.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {sortedEntries.length === 0 ? (
            <p className="py-3 text-center text-xs text-muted-foreground">No data</p>
          ) : (
            <>
              <ul className="flex flex-col gap-1.5">
                {sortedEntries.map(([label, count], i) => (
                  <li key={label} className="flex items-center justify-between gap-2 text-xs">
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="inline-block size-2 shrink-0 rounded-full"
                        style={{ backgroundColor: DOT_COLORS[i % DOT_COLORS.length] }}
                      />
                      <span className="truncate">{label}</span>
                    </span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">{count}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-2 flex items-center justify-between border-t pt-2 text-xs font-medium">
                <span>{days > 1 ? `Total over ${days} days` : "Total"}</span>
                <span className="tabular-nums">
                  {total.toLocaleString()}
                  {days > 1 && <span className="font-normal text-muted-foreground"> · ≈{Math.round(total / days).toLocaleString()} a day</span>}
                </span>
              </div>
            </>
          )}
        </section>

        <section className="rounded-md border px-3 py-3">
          <h3 className="mb-2 text-xs font-semibold">Layout</h3>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Racks</span>
              <span className="tabular-nums">{rackCount}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Items</span>
              <span className="tabular-nums">{itemCount}</span>
            </div>
          </div>
          {editableLayout && projectId && setupId && (
            <LayoutExcelControls
              store={store}
              projectId={projectId}
              setupId={setupId}
              mode="download"
            />
          )}
          <SheetTrigger asChild>
            <button
              type="button"
              className="mt-2 text-xs text-primary hover:underline"
            >
              View detail
            </button>
          </SheetTrigger>
          {projectId && setupId && <LayoutEditInWords key={setupId} projectId={projectId} setupId={setupId} />}
        </section>
      </div>

      <SheetContent side="right" className="w-[900px] sm:max-w-[900px] max-w-[90vw] overflow-hidden p-0">
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="text-sm">Rack Detail</SheetTitle>
          <SheetDescription className="text-xs">
            Rack → Face → Level slot details
          </SheetDescription>
        </SheetHeader>
        <RackDetailView store={store} />
      </SheetContent>
    </Sheet>
  );
}

