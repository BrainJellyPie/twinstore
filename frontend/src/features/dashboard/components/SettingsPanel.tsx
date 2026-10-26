import { useMemo, useState } from "react";
import { TableProperties } from "lucide-react";
import type { Store, Persona } from "@/shared/types/domain";
import type { RunSummary } from "@/shared/api/client";
import { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/shared/components/ui/sheet";
import { Button } from "@/shared/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/shared/components/ui/toggle-group";
import { LayoutExcelControls } from "@/features/layouts/components/LayoutExcelControls";
import { RackDetailView } from "./RackDetailView";
import { currencyCode } from "@/shared/utils/money";
import { LayoutEditInWords } from "./LayoutEditInWords";
import { DeleteLayout } from "@/features/layouts/components/DeleteLayout";
import { RenameLayout } from "@/features/layouts/components/RenameLayout";
import { formatWeeklyHours } from "@/features/layouts/weeklyHours";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { storeTypeLabel } from "@/shared/i18n/storeLabels";
import { personaLabel } from "@/shared/i18n/personaLabels";
import { EmptyFloorStart } from "./EmptyFloorStart";

type CustomerTab = "identity" | "purpose" | "age" | "gender";
const CUSTOMER_TABS: { value: CustomerTab; label: MessageKey }[] = [
  { value: "identity", label: "storeTabPersona" },
  { value: "purpose", label: "kpiPurpose" },
  { value: "age", label: "storeTabAgeGroup" },
  { value: "gender", label: "kpiGender" },
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
  const { locale, t } = useI18n();
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
      <div className="space-y-3 px-3 pt-3 text-xs text-muted-foreground">
        <p>{t("storeTabNoFloor")}</p>
        <EmptyFloorStart />
        {/* A layout added by mistake can go before it has a floor. */}
        {projectId && setupId && <DeleteLayout key={`delete:${setupId}`} projectId={projectId} setupId={setupId} />}
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
    [t("storeName"), store.name || "—"],
    [t("address"), location || "—"],
    [t("storeType"), store.type ? storeTypeLabel(store.type, locale) : "—"],
    [t("priceCurrency"), currencyCode(summary?.currency ?? store.currency ?? undefined)],
    [t("openingHours"), formatWeeklyHours(store.weekly_schedule ?? [], locale)],
  ];

  return (
    <Sheet>
      <div className="flex flex-col gap-3 py-3">
        <section className="rounded-md border px-3 py-3">
          <h3 className="mb-2 text-xs font-semibold">{t("storeTabInfo")}</h3>
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
          <h3 className="mb-2 text-xs font-semibold">{t("storeTabCustomers")}</h3>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={tab}
            onValueChange={(v) => {
              if (v) setTab(v as CustomerTab);
            }}
            className="mb-3"
            aria-label={t("storeTabDistribution")}
          >
            {CUSTOMER_TABS.map((item) => (
              <ToggleGroupItem
                key={item.value}
                value={item.value}
                className="text-xs"
              >
                {t(item.label)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          {sortedEntries.length === 0 ? (
            <p className="py-3 text-center text-xs text-muted-foreground">{t("dashNoData")}</p>
          ) : (
            <>
              {/* One hue: the bar is each group's size against the largest, the figure its share of everyone. */}
              <ul className="flex flex-col gap-2">
                {sortedEntries.map(([label, count]) => {
                  const name = tab === "age" || tab === "gender" ? personaLabel(label, t) : label;
                  return (
                    <li key={label} className="text-xs">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate" title={name}>{name}</span>
                        <span className="shrink-0 tabular-nums">
                          {count.toLocaleString(locale)}
                          <span className="ml-1.5 inline-block w-8 text-right text-muted-foreground">{count / total < 0.005 ? "<1" : Math.round((count / total) * 100)}%</span>
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-foreground/[0.06]" aria-hidden>
                        <div className="h-full rounded-full" style={{ width: `${(count / sortedEntries[0]![1]) * 100}%`, background: "var(--viz-1)" }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
              <div className="mt-2 flex items-center justify-between border-t pt-2 text-xs font-medium">
                <span>{days > 1 ? t("storeTabTotalDays", { days }) : t("storeTabTotal")}</span>
                <span className="tabular-nums">
                  {total.toLocaleString(locale)}
                  {days > 1 && <span className="font-normal text-muted-foreground"> · {t("storeTabPerDay", { count: Math.round(total / days) })}</span>}
                </span>
              </div>
            </>
          )}
        </section>

        <section className="rounded-md border px-3 py-3">
          <h3 className="mb-2 text-xs font-semibold">{t("optLayout")}</h3>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{t("dashRacks")}</span>
              <span className="tabular-nums">{rackCount}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{t("storeTabItems")}</span>
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
            <Button type="button" variant="outline" size="sm" className="mt-2 h-8 gap-1.5 text-xs">
              <TableProperties className="size-3.5" aria-hidden /> {t("storeTabViewDetail")}
            </Button>
          </SheetTrigger>
          {projectId && setupId && <RenameLayout key={`rename:${projectId}:${setupId}`} projectId={projectId} setupId={setupId} />}
          {projectId && setupId && <LayoutEditInWords key={setupId} projectId={projectId} setupId={setupId} />}
          {projectId && setupId && <DeleteLayout key={`delete:${setupId}`} projectId={projectId} setupId={setupId} />}
        </section>
      </div>

      <SheetContent side="right" className="w-[900px] sm:max-w-[900px] max-w-[90vw] overflow-hidden p-0">
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="text-sm">{t("storeTabRackDetail")}</SheetTitle>
          <SheetDescription className="text-xs">
            {t("storeTabRackDetailHint")}
          </SheetDescription>
        </SheetHeader>
        <RackDetailView store={store} />
      </SheetContent>
    </Sheet>
  );
}

