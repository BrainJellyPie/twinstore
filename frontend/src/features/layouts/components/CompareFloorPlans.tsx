import { RequestError } from "@/shared/components/RequestError";
import type { MessageKey } from "@/shared/i18n/messages";
import type { StoreDesign } from "@/shared/types/domain";
import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { INTERIOR_COLOR_FIELDS } from "@/features/store-viewer/realistic/designThemes";
import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { rackDiningSeats } from "@/shared/utils/dining";
import { FloorPlanPreview } from "./FloorPlanPreview";
import { formatWeeklyHours } from "../weeklyHours";
import { useI18n } from "@/shared/i18n/i18n";
import { templateName } from "@/shared/i18n/storeLabels";

const DESIGN_LABELS: Record<StoreDesign, MessageKey> = {
  classic: "planDesignClassic", warm: "planDesignWarm", minimal: "planDesignMinimal", industrial: "planDesignIndustrial",
  botanical: "planDesignBotanical", luxury: "planDesignLuxury", coastal: "planDesignCoastal", terracotta: "planDesignTerracotta",
  nordic: "planDesignNordic", retro: "planDesignRetro",
};

export function CompareFloorPlans({ store, areas, templateId, currency }: {
  store: Store;
  areas: api.ReservedArea[];
  templateId: string;
  currency: string;
}) {
  const { t, locale } = useI18n();
  const number = (value: number) => new Intl.NumberFormat(locale).format(value);
  const [open, setOpen] = useState(false);
  const id = useId();
  const request = { template_id: templateId, seed: 0, currency };
  const baseline = useQuery({
    queryKey: ["store-template-preview", request],
    queryFn: ({ signal }) => api.previewStoreTemplate(request, signal),
    enabled: open, staleTime: Infinity,
  });
  const frame: [number, number] = [
    Math.max(store.grid_size[0], baseline.data?.grid_size[0] ?? 0),
    Math.max(store.grid_size[1], baseline.data?.grid_size[1] ?? 0),
  ];
  const plans = baseline.data ? [
    { id: "default", label: t("planCompareDefault"), store: baseline.data, areas: [] as api.ReservedArea[] },
    { id: "current", label: t("planCompareCurrent"), store, areas },
  ] : [];
  const metrics: { label: MessageKey; value: (plan: typeof plans[number]) => string | number }[] = [
    { label: "planCompareSize", value: (plan) => plan.store.grid_size.map(number).join("×") },
    { label: "planCompareDisplays", value: (plan) => plan.store.racks.filter((rack) => rack.slots.length).length },
    { label: "planCompareProducts", value: (plan) => new Set(plan.store.racks.flatMap((rack) => rack.slots.flatMap((slot) => slot.items.map((item) => item.sku)))).size },
    { label: "planCompareSeating", value: (plan) => { const tables = plan.store.racks.filter((rack) => rack.type === "table").length; return `${number(tables)} / ${number(plan.store.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0))}`; } },
    { label: "planCompareCounters", value: (plan) => plan.store.racks.filter((rack) => rack.type === "counter").length },
    { label: "planCompareAreas", value: (plan) => plan.areas.length },
    { label: "planCompareDesign", value: (plan) => (() => {
      const design = t(DESIGN_LABELS[plan.store.design_theme ?? "classic"]);
      return INTERIOR_COLOR_FIELDS.some(([key]) => plan.store.design_colors?.[key] != null)
        ? t("planCustomColors", { design }) : design;
    })() },
    { label: "planCompareHours", value: (plan) => formatWeeklyHours(plan.store.weekly_schedule, locale) },
  ];
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><button type="button" className="w-full rounded-md border px-2 py-1 text-xs hover:bg-muted">{t("compareWithDefault")}</button></DialogTrigger>
    <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,900px)]">
      <DialogHeader>
        <DialogTitle>{t("planCompareTitle")}</DialogTitle>
        <DialogDescription>{t("planCompareDescription")}</DialogDescription>
      </DialogHeader>
      <div className="min-h-0 space-y-4 overflow-y-auto">
        {baseline.isPending && <p role="status" className="text-sm">{t("planCompareLoading")}</p>}
        {baseline.isError && <RequestError error={baseline.error}><button type="button" className="underline" onClick={() => void baseline.refetch()}>{t("planCompareRetry")}</button></RequestError>}
        {baseline.isSuccess && <>
          <div className="grid gap-4 sm:grid-cols-2">
            {plans.map((plan, index) => <section key={plan.id} aria-labelledby={`${id}-plan-${index}`} className="min-w-0 space-y-2">
              <h3 id={`${id}-plan-${index}`} className="text-sm font-medium">{plan.label}</h3>
              <FloorPlanPreview store={plan.store} areas={plan.areas} previewFrame={frame} name={plan.id === "default" ? templateName(templateId, plan.store.name, locale) : plan.store.name} />
            </section>)}
          </div>
          <p className="text-xs text-muted-foreground">{t("planLegend", { inLabel: t("planIn"), outLabel: t("planOut") })}</p>
          <table className="w-full table-fixed text-left text-xs" aria-label={t("planCompareTable")}>
            <thead><tr><th scope="col" className="w-[36%] p-2">{t("planCompareDetails")}</th>{plans.map((plan) => <th scope="col" key={plan.id} className="p-2">{plan.label}</th>)}</tr></thead>
            <tbody>{metrics.map((metric) => <tr key={metric.label} className="border-t">
              <th scope="row" className="p-2 font-normal">{t(metric.label)}</th>
              {plans.map((plan) => { const value = metric.value(plan); return <td key={plan.id} className="break-words p-2 align-top">{typeof value === "number" ? number(value) : value}</td>; })}
            </tr>)}</tbody>
          </table>
          <p className="text-xs text-muted-foreground">{t("planCompareLimits")}</p>
        </>}
      </div>
    </DialogContent>
  </Dialog>;
}
