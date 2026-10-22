import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { rackDiningSeats } from "@/shared/utils/dining";
import { FloorPlanPreview } from "./FloorPlanPreview";
import { formatWeeklyHours } from "../weeklyHours";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";
import { templateName } from "@/shared/i18n/storeLabels";
import { paletteLabel } from "../optionLabels";

export function CompareFloorPlans({ store, areas, templateId, currency }: {
  store: Store;
  areas: api.ReservedArea[];
  templateId: string;
  currency: string;
}) {
  const { locale, t } = useI18n();
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
    { label: t("layFormatDefaultPlan"), store: baseline.data, areas: [] as api.ReservedArea[] },
    { label: t("layYourCurrentOptions"), store, areas },
  ] : [];
  const metrics: { label: MessageKey; value: (plan: typeof plans[number]) => string | number }[] = [
    { label: "layFloorSizeCells", value: (plan) => plan.store.grid_size.join("×") },
    { label: "layProductDisplays", value: (plan) => plan.store.racks.filter((rack) => rack.slots.length).length },
    { label: "layUniqueProducts", value: (plan) => new Set(plan.store.racks.flatMap((rack) => rack.slots.flatMap((slot) => slot.items.map((item) => item.sku)))).size },
    { label: "layTablesSeats", value: (plan) => { const tables = plan.store.racks.filter((rack) => rack.type === "table").length; return `${tables} / ${plan.store.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0)}`; } },
    { label: "layCheckoutCounters", value: (plan) => plan.store.racks.filter((rack) => rack.type === "counter").length },
    { label: "layReservedAreas", value: (plan) => plan.areas.length },
    { label: "layInteriorDesign", value: (plan) => paletteLabel(plan.store.design_theme, plan.store.design_colors, t) },
    { label: "layOperatingHours", value: (plan) => formatWeeklyHours(plan.store.weekly_schedule, locale) },
  ];
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><button type="button" className="w-full rounded-md border px-2 py-1 text-xs hover:bg-muted">{t("compareWithDefault")}</button></DialogTrigger>
    <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,900px)]">
      <DialogHeader>
        <DialogTitle>{t("layCompareFloorPlans")}</DialogTitle>
        <DialogDescription>{t("layCompareFloorPlansHint")}</DialogDescription>
      </DialogHeader>
      <div className="min-h-0 space-y-4 overflow-y-auto">
        {baseline.isPending && <p role="status" className="text-sm">{t("layLoadingFormatDefault")}</p>}
        {baseline.isError && <p role="alert" className="text-sm text-destructive">{t("layFormatDefaultFailed")} {baseline.error.message} <button type="button" className="underline" onClick={() => void baseline.refetch()}>{t("layRetryComparison")}</button></p>}
        {baseline.isSuccess && <>
          <div className="grid gap-4 sm:grid-cols-2">
            {plans.map((plan, index) => <section key={plan.label} aria-labelledby={`${id}-plan-${index}`} className="min-w-0 space-y-2">
              <h3 id={`${id}-plan-${index}`} className="text-sm font-medium">{plan.label}</h3>
              <FloorPlanPreview store={plan.store} areas={plan.areas} previewFrame={frame} name={templateName(templateId, plan.store.name, locale)} />
            </section>)}
          </div>
          <p className="text-xs text-muted-foreground">{t("floorPlanLegend")}</p>
          <table className="w-full table-fixed text-left text-xs" aria-label={t("layFloorPlanComparison")}>
            <thead><tr><th scope="col" className="w-[36%] p-2">{t("layLayoutDetails")}</th>{plans.map((plan) => <th scope="col" key={plan.label} className="p-2">{plan.label}</th>)}</tr></thead>
            <tbody>{metrics.map((metric) => <tr key={metric.label} className="border-t">
              <th scope="row" className="p-2 font-normal">{t(metric.label)}</th>
              {plans.map((plan) => <td key={plan.label} className="break-words p-2 align-top">{metric.value(plan)}</td>)}
            </tr>)}</tbody>
          </table>
          <p className="text-xs text-muted-foreground">{t("layCompareFootnote")}</p>
        </>}
      </div>
    </DialogContent>
  </Dialog>;
}
