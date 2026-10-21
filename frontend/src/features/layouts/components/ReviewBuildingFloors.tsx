import { useId, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { INTERIOR_DESIGNS } from "@/features/store-viewer/realistic/designThemes";
import * as api from "@/shared/api/client";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/components/ui/dialog";
import { templateRequest, validBuildingFloors, validTemplateChoice, type BuildingFloorChoice } from "../templateOptions";
import { FloorPlanPreview } from "./FloorPlanPreview";

interface Props {
  floors: BuildingFloorChoice[];
  onEdit: (index: number) => void;
}

export function ReviewBuildingFloors({ floors, onEdit }: Props) {
  const [open, setOpen] = useState(false);
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted">Review all floors</button></DialogTrigger>
    <DialogContent className="flex max-h-[92dvh] flex-col overflow-hidden sm:max-w-[min(92vw,1000px)]">
      <DialogHeader>
        <DialogTitle>Review building floors</DialogTitle>
        <DialogDescription>Compare every floor at the same cell scale before creating the building. Floors are simulated independently.</DialogDescription>
      </DialogHeader>
      <FloorReviews floors={floors} onEdit={(index) => { setOpen(false); onEdit(index); }} />
    </DialogContent>
  </Dialog>;
}

function FloorReviews({ floors, onEdit }: Props) {
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
  const checkouts = stores.reduce((sum, store) => sum + store.racks.filter((rack) => rack.type === "counter").length, 0);
  return <>
    <div className="space-y-1 text-xs" aria-live="polite">
      <p>{ready} of {floors.length} floor previews ready</p>
      {ready === floors.length && <p>{stores.reduce((sum, store) => sum + store.grid_size[0] * store.grid_size[1], 0)} total floor cells · {tables} dining tables · {tables * 4} seats · {checkouts} checkout counters</p>}
      {!validBuildingFloors(floors) && <p role="alert" className="text-destructive">Each floor needs a unique label and valid layout values before creating the building.</p>}
    </div>
    <div className="grid min-h-0 gap-4 overflow-y-auto sm:grid-cols-2">
      {floors.map((floor, index) => {
        const preview = previews[index];
        const store = preview?.data;
        const valid = validTemplateChoice(floor.choice);
        const tableCount = store?.racks.filter((rack) => rack.type === "table").length ?? 0;
        return <section key={index} aria-labelledby={`${id}-floor-${index}`} className="min-w-0 space-y-2 rounded-lg border p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h3 id={`${id}-floor-${index}`} className="min-w-0 break-words text-sm font-medium">{index + 1}F · {floor.label.trim() || "Unnamed floor"}</h3>
            <button type="button" className="shrink-0 rounded border px-2 py-1 text-xs hover:bg-muted" onClick={() => onEdit(index)}>Edit floor {index + 1}</button>
          </div>
          {!valid ? <p role="alert" className="text-xs text-destructive">Enter valid grid dimensions, product and table counts, and reserved-area values for this floor.</p>
            : preview?.isError ? <p role="alert" className="text-xs text-destructive">{preview.error.message} <button type="button" className="underline" onClick={() => void preview.refetch()}>Retry floor {index + 1}</button></p>
              : !preview || preview.isPending ? <p role="status" className="text-xs">Loading floor {index + 1}…</p>
                : store && <>
                  <p className="text-xs text-muted-foreground">{store.name} · {store.grid_size.join("×")} cells · {store.currency ?? floor.choice.currency}</p>
                  <FloorPlanPreview store={store} areas={floor.choice.reserved_areas ?? []} previewFrame={frame} />
                  <p className="text-xs">{store.racks.filter((rack) => rack.slots.length).length} displays · {tableCount} dining tables · {tableCount * 4} seats · {store.racks.filter((rack) => rack.type === "counter").length} checkout counters</p>
                  <p className="text-xs text-muted-foreground">{INTERIOR_DESIGNS[store.design_theme ?? "classic"].label} · {floor.choice.reserved_areas?.length ?? 0} reserved areas</p>
                </>}
        </section>;
      })}
    </div>
  </>;
}
