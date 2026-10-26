import { RequestError } from "@/shared/components/RequestError";
import { rackDiningSeats } from "@/shared/utils/dining";
import { useId, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import { templateRequest, validBuildingFloors, validTemplateChoice, type BuildingFloorChoice } from "../templateOptions";
import { FloorPlanPreview } from "./FloorPlanPreview";
import { formatWeeklyHours } from "../weeklyHours";
import { useI18n } from "@/shared/i18n/i18n";
import { templateName } from "@/shared/i18n/storeLabels";
import { paletteLabel } from "../optionLabels";

interface Props {
  floors: BuildingFloorChoice[];
  onEdit: (index: number) => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function ReviewBuildingFloors({ floors, onEdit, open: controlledOpen, onOpenChange }: Props) {
  const { t } = useI18n();
  const [localOpen, setLocalOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const setOpen = (next: boolean) => { setLocalOpen(next); onOpenChange?.(next); };
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted">{t("layReviewAllFloors")}</button></DialogTrigger>
    <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,1000px)] [@media(max-height:500px)]:gap-3 [@media(max-height:500px)]:p-4">
      <DialogHeader className="shrink-0">
        <DialogTitle className="[@media(max-height:500px)]:pr-6 [@media(max-height:500px)]:text-lg">{t("layReviewBuildingFloors")}</DialogTitle>
        <DialogDescription className="[@media(max-height:500px)]:sr-only">{t("layReviewBuildingHint")}</DialogDescription>
      </DialogHeader>
      <FloorReviews floors={floors} onEdit={(index) => { setOpen(false); onEdit(index); }} />
    </DialogContent>
  </Dialog>;
}

function FloorReviews({ floors, onEdit }: Props) {
  const { locale, t } = useI18n();
  const id = useId();
  const requests = floors.map((floor) => {
    if (!validTemplateChoice(floor.choice)) return null;
    const { requirements: _brief, ...request } = templateRequest(floor.choice);
    return request;
  });
  const uniqueRequests = [...new Map(requests.flatMap((request) => request ? [[JSON.stringify(request), request] as const] : [])).values()];
  const queries = useQueries({ queries: uniqueRequests.map((request) => ({
      queryKey: ["store-template-preview", request],
      queryFn: ({ signal }: { signal: AbortSignal }) => api.previewStoreTemplate(request, signal),
      staleTime: Infinity,
  })) });
  const previews = requests.map((request) => request ? queries[uniqueRequests.findIndex((candidate) => JSON.stringify(candidate) === JSON.stringify(request))] : undefined);
  const ready = previews.filter((preview) => preview?.isSuccess).length;
  const stores = previews.flatMap((preview) => preview?.isSuccess ? [preview.data] : []);
  const frame: [number, number] = [Math.max(1, ...stores.map((store) => store.grid_size[0])), Math.max(1, ...stores.map((store) => store.grid_size[1]))];
  const tables = stores.reduce((sum, store) => sum + store.racks.filter((rack) => rack.type === "table").length, 0);
  const seats = stores.reduce((sum, store) => sum + store.racks.reduce((total, rack) => total + rackDiningSeats(rack), 0), 0);
  const checkouts = stores.reduce((sum, store) => sum + store.racks.filter((rack) => rack.type === "counter").length, 0);
  return <>
    <div className="space-y-1 text-xs" aria-live="polite">
      <p>{t("layFloorPreviewsReady", { ready, total: floors.length })}</p>
      {ready === floors.length && <p>{t("layBuildingTotals", { cells: stores.reduce((sum, store) => sum + store.grid_size[0] * store.grid_size[1], 0), tables, seats, checkouts })}</p>}
      {!validBuildingFloors(floors) && <p role="alert" className="text-destructive">{t("layBuildingInvalidCreate")}</p>}
    </div>
    <div className="grid grid-cols-1 min-h-0 gap-4 overflow-y-auto sm:grid-cols-2">
      {floors.map((floor, index) => {
        const preview = previews[index];
        const store = preview?.data;
        const valid = validTemplateChoice(floor.choice);
        const tableCount = store?.racks.filter((rack) => rack.type === "table").length ?? 0;
        return <section key={index} aria-labelledby={`${id}-floor-${index}`} className="min-w-0 space-y-2 rounded-lg border p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h3 id={`${id}-floor-${index}`} className="min-w-0 break-words text-sm font-medium">{t("layNamedFloor", { number: index + 1, name: floor.label.trim() || t("layUnnamedFloor") })}</h3>
            <button type="button" className="shrink-0 rounded border px-2 py-1 text-xs hover:bg-muted" onClick={() => onEdit(index)}>{t("layEditFloorNumber", { number: index + 1 })}</button>
          </div>
          {!valid ? <p role="alert" className="text-xs text-destructive">{t("layFloorInvalid")}</p>
            : preview?.isError ? <RequestError error={preview.error}><button type="button" className="underline" onClick={() => void preview.refetch()}>{t("layRetryFloor", { number: index + 1 })}</button></RequestError>
              : !preview || preview.isPending ? <p role="status" className="text-xs">{t("layLoadingFloor", { number: index + 1 })}</p>
                : store && <>
                  <p className="text-xs text-muted-foreground">{t("layFloorStoreLine", { name: templateName(floor.choice.templateId, store.name, locale), size: store.grid_size.join("×"), currency: store.currency ?? floor.choice.currency })}</p>
                  <FloorPlanPreview store={store} areas={floor.choice.reserved_areas ?? []} previewFrame={frame} name={templateName(floor.choice.templateId, store.name, locale)} />
                  <p className="text-xs">{t("layFloorStats", { displays: store.racks.filter((rack) => rack.slots.length).length, tables: tableCount, seats: store.racks.reduce((sum, rack) => sum + rackDiningSeats(rack), 0), counters: store.racks.filter((rack) => rack.type === "counter").length })}</p>
                  <p className="text-xs text-muted-foreground">{paletteLabel(store.design_theme, store.design_colors, t)} · {t("layReservedAreaCount", { count: floor.choice.reserved_areas?.length ?? 0 })}</p>
                  <p className="break-words text-xs text-muted-foreground">{t("layOperatingHoursLine", { hours: formatWeeklyHours(store.weekly_schedule, locale) })}</p>
                </>}
        </section>;
      })}
    </div>
  </>;
}
