import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { resolveInteriorPalette } from "@/features/store-viewer/realistic/designThemes";
import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import type { Store } from "@/shared/types/domain";
import { rackDiningSeats } from "@/shared/utils/dining";
import { FloorPlanPreview } from "./FloorPlanPreview";
import { formatWeeklyHours } from "../weeklyHours";

export function CompareFloorPlans({ store, areas, templateId, currency }: {
  store: Store;
  areas: api.ReservedArea[];
  templateId: string;
  currency: string;
}) {
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
    { label: "Format default", store: baseline.data, areas: [] as api.ReservedArea[] },
    { label: "Your current options", store, areas },
  ] : [];
  const metrics: { label: string; value: (plan: typeof plans[number]) => string | number }[] = [
    { label: "Floor size (cells)", value: (plan) => plan.store.grid_size.join("×") },
    { label: "Product displays", value: (plan) => plan.store.racks.filter((rack) => rack.slots.length).length },
    { label: "Unique products", value: (plan) => new Set(plan.store.racks.flatMap((rack) => rack.slots.flatMap((slot) => slot.items.map((item) => item.sku)))).size },
    { label: "Dining tables / seats", value: (plan) => { const tables = plan.store.racks.filter((rack) => rack.type === "table").length; return `${tables} / ${plan.store.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0)}`; } },
    { label: "Checkout counters", value: (plan) => plan.store.racks.filter((rack) => rack.type === "counter").length },
    { label: "Reserved areas", value: (plan) => plan.areas.length },
    { label: "Interior design", value: (plan) => resolveInteriorPalette(plan.store.design_theme, plan.store.design_colors).label },
    { label: "Operating hours", value: (plan) => formatWeeklyHours(plan.store.weekly_schedule) },
  ];
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><button type="button" className="w-full rounded-md border px-2 py-1 text-xs hover:bg-muted">Compare with default</button></DialogTrigger>
    <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,900px)]">
      <DialogHeader>
        <DialogTitle>Compare floor plans</DialogTitle>
        <DialogDescription>Review the format's starting layout alongside your current options. Both previews use the same cell scale.</DialogDescription>
      </DialogHeader>
      <div className="min-h-0 space-y-4 overflow-y-auto">
        {baseline.isPending && <p role="status" className="text-sm">Loading the format default…</p>}
        {baseline.isError && <p role="alert" className="text-sm text-destructive">Could not load the format default. {baseline.error.message} <button type="button" className="underline" onClick={() => void baseline.refetch()}>Retry comparison</button></p>}
        {baseline.isSuccess && <>
          <div className="grid gap-4 sm:grid-cols-2">
            {plans.map((plan, index) => <section key={plan.label} aria-labelledby={`${id}-plan-${index}`} className="min-w-0 space-y-2">
              <h3 id={`${id}-plan-${index}`} className="text-sm font-medium">{plan.label}</h3>
              <FloorPlanPreview store={plan.store} areas={plan.areas} previewFrame={frame} />
            </section>)}
          </div>
          <p className="text-xs text-muted-foreground">Blue: cold · Amber: display · Green IN: entrance · Rose OUT: exit · Split IN/OUT: shared gate · Slate: checkout · Purple: seating</p>
          <table className="w-full table-fixed text-left text-xs" aria-label="Floor plan comparison">
            <thead><tr><th scope="col" className="w-[36%] p-2">Layout details</th>{plans.map((plan) => <th scope="col" key={plan.label} className="p-2">{plan.label}</th>)}</tr></thead>
            <tbody>{metrics.map((metric) => <tr key={metric.label} className="border-t">
              <th scope="row" className="p-2 font-normal">{metric.label}</th>
              {plans.map((plan) => <td key={plan.label} className="break-words p-2 align-top">{metric.value(plan)}</td>)}
            </tr>)}</tbody>
          </table>
          <p className="text-xs text-muted-foreground">The format default uses its original size, assortment and seed 0. This comparison does not change your settings or save a layout.</p>
        </>}
      </div>
    </DialogContent>
  </Dialog>;
}
