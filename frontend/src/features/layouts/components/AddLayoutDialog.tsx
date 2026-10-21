// Approach radio:
//   - "Import from..." (default): clone an existing layout as parent (API mode=racks_and_items).
//   - "Build from scratch": create an empty setup (API mode=empty).
// The "racks only" option exists in the API (mode=racks) but is intentionally not
// exposed in this dialog.
//
// On success, useCreateLayout's onSuccess switches selectedSetupId to the new layout
// and this component closes via onOpenChange(false).

import { useEffect, useId, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { previewFloorPlan } from "@/shared/api/client";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { cn } from "@/shared/utils/cn";

import { useCreateLayout } from "../hooks/useCreateLayout";
import { BuildingPicker } from "./BuildingPicker";
import { TemplatePicker } from "./TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, buildingPreset, choiceFromGeneration, validBuildingFloors, validTemplateChoice, type TemplateChoice } from "../templateOptions";
import type { Layout } from "../hooks/useLayouts";

type Approach = "import" | "empty" | "template" | "plan" | "building";

const labelClass = "text-sm font-medium";

export interface AddLayoutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  parentSetupId: string;
  layouts: Layout[];
  defaultCurrency?: string;
}

function resolveDefaultParent(parentSetupId: string, layouts: Layout[]): string {
  if (parentSetupId.length > 0) return parentSetupId;
  return layouts[0]?.id ?? "";
}

export function AddLayoutDialog({
  open,
  onOpenChange,
  projectId,
  parentSetupId,
  layouts,
  defaultCurrency = "USD",
}: AddLayoutDialogProps) {
  const createLayout = useCreateLayout();

  const [name, setName] = useState<string>(() => `layout ${layouts.length + 1}`);
  const [approach, setApproach] = useState<Approach>("import");
  const [selectedParentId, setSelectedParentId] = useState<string>(() =>
    resolveDefaultParent(parentSetupId, layouts),
  );
  const [template, setTemplate] = useState<TemplateChoice>({ ...DEFAULT_TEMPLATE_CHOICE, currency: defaultCurrency });
  const [floors, setFloors] = useState(() => buildingPreset("department", defaultCurrency));
  const [planFile, setPlanFile] = useState<File | null>(null);
  const [planReader, setPlanReader] = useState<"auto" | "classic">("auto");
  const [planPage, setPlanPage] = useState(1);
  const [planRotation, setPlanRotation] = useState(0);
  const [planFileVersion, setPlanFileVersion] = useState(0);
  const previewScope = useId();
  const planPreview = useQuery({
    queryKey: ["floorplan-preview", projectId, previewScope, planFileVersion, planPage, planRotation],
    queryFn: ({ signal }) => previewFloorPlan(projectId, planFile!, { pageNumber: planPage, rotation: planRotation, signal }),
    enabled: open && approach === "plan" && planFile !== null && Number.isInteger(planPage) && planPage >= 1,
    retry: false, staleTime: Infinity, gcTime: 0,
  });

  // Restore defaults on each open; also reset the prior mutation's error state.
  useEffect(() => {
    if (open) {
      setName(`layout ${layouts.length + 1}`);
      setApproach("import");
      setPlanFile(null);
      setPlanPage(1);
      setPlanRotation(0);
      setSelectedParentId(resolveDefaultParent(parentSetupId, layouts));
      setTemplate((current) => ({ ...current, currency: defaultCurrency, sourceSetupId: undefined }));
      setFloors((current) => current.map((floor) => ({ ...floor, choice: { ...floor.choice, currency: defaultCurrency } })));
      createLayout.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const trimmed = name.trim();
  const sourceLayout = layouts.find((layout) => layout.id === parentSetupId);
  const canSubmit =
    trimmed.length > 0 &&
    !createLayout.isPending &&
    (approach !== "import" || selectedParentId.length > 0) &&
    (approach !== "plan" || (planFile !== null && planPage >= 1 && Number.isInteger(planPage) && planPreview.isSuccess)) &&
    (approach !== "template" || validTemplateChoice(template)) &&
    (approach !== "building" || (trimmed.length <= 160 && validBuildingFloors(floors)));

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    createLayout.mutate(
      {
        projectId,
        name: trimmed,
        source:
          approach === "building"
            ? { kind: "building", floors }
            : approach === "import"
            ? { kind: "import", parentSetupId: selectedParentId }
            : approach === "template"
              ? { kind: "template", ...template }
              : approach === "plan" && planFile
                ? { kind: "plan", file: planFile, reader: planReader, pageNumber: planPage, rotation: planRotation }
                : { kind: "empty" },
      },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("max-h-[90dvh] overflow-y-auto", (approach === "template" || approach === "building") ? "sm:max-w-[760px]" : "sm:max-w-[420px]")}>
        <DialogHeader>
          <DialogTitle>Add layout</DialogTitle>
          <DialogDescription className="sr-only">Create a layout from an existing store, a template, an image or a PDF floor plan.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className={labelClass} htmlFor="add-layout-name">
              {approach === "building" ? "Building name" : "Layout name"}
            </label>
            <Input
              id="add-layout-name"
              data-testid="add-layout-name-input"
              value={name}
              maxLength={approach === "building" ? 160 : 300}
              placeholder="e.g. layout 2"
              disabled={createLayout.isPending}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <RadioGroup
              value={approach}
              onValueChange={(value: string) => setApproach(value as Approach)}
              className="gap-3"
              aria-label="Layout creation approach"
            >
              <div className="space-y-2">
                <label
                  className="flex items-center gap-2 text-sm"
                  htmlFor="add-layout-approach-import"
                >
                  <RadioGroupItem
                    id="add-layout-approach-import"
                    data-testid="add-layout-approach-import"
                    value="import"
                    disabled={createLayout.isPending}
                  />
                  Import from...
                </label>
                {approach === "import" && (
                  <Select
                    value={selectedParentId}
                    onValueChange={setSelectedParentId}
                    disabled={createLayout.isPending}
                  >
                    <SelectTrigger
                      id="add-layout-parent"
                      data-testid="add-layout-parent-trigger"
                      className="w-full"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {layouts.map((layout) => (
                        <SelectItem key={layout.id} value={layout.id}>
                          {layout.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <label
                className="flex items-center gap-2 text-sm"
                htmlFor="add-layout-approach-empty"
              >
                <RadioGroupItem
                  id="add-layout-approach-empty"
                  data-testid="add-layout-approach-empty"
                  value="empty"
                  disabled={createLayout.isPending}
                />
                Build from scratch
              </label>

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-template">
                  <RadioGroupItem
                    id="add-layout-approach-template"
                    value="template"
                    disabled={createLayout.isPending}
                  />
                  Generate a store from a template
                </label>
                {approach === "template" && <>
                  {sourceLayout?.generation && <div className="space-y-1 rounded-md border p-3 text-xs">
                    <button type="button" className="font-medium text-primary underline" onClick={() => setTemplate(choiceFromGeneration(sourceLayout.generation!, sourceLayout.id))}>
                      Reuse options from {sourceLayout.name}
                    </button>
                    <p className="text-muted-foreground">Bring back the saved template settings and design brief, then change them to create an alternative. Manual fixture edits and uploaded products are kept by the import option.</p>
                    {template.sourceSetupId === sourceLayout.id && <p role="status">The new layout will be linked to {sourceLayout.name}. The source layout stays unchanged.</p>}
                  </div>}
                  <TemplatePicker value={template} budgetCurrency={defaultCurrency} onChange={setTemplate} />
                </>}
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-building">
                  <RadioGroupItem id="add-layout-approach-building" value="building" disabled={createLayout.isPending} />
                  Multi-floor store
                </label>
                {approach === "building" && <BuildingPicker floors={floors} defaultCurrency={defaultCurrency} onChange={setFloors} />}
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-plan">
                  <RadioGroupItem id="add-layout-approach-plan" value="plan" disabled={createLayout.isPending} />
                  From a floor plan — sketch, CAD export or PDF
                </label>
                {approach === "plan" && (
                  <div className="space-y-2 rounded-xl border bg-foreground/[0.02] p-3">
                    <label className="flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed border-foreground/15 px-3 py-5 text-center text-sm transition-colors hover:border-primary">
                      <span className="font-medium">{planFile ? planFile.name : "Choose a plan image"}</span>
                      <span className="text-xs text-muted-foreground">Walls, fixtures as boxes, a gap for the door. Words like “drinks” on a box pick its products.</span>
                      <input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" className="hidden" disabled={createLayout.isPending}
                        aria-label="Choose floor plan file" onChange={(e) => {
                          setPlanFile(e.target.files?.[0] ?? null);
                          setPlanFileVersion((version) => version + 1);
                          setPlanPage(1);
                          setPlanRotation(0);
                          e.target.value = "";
                        }} />
                    </label>
                    {planFile && <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <label>Page {planPreview.data ? `of ${planPreview.data.page_count}` : ""}
                          <Input aria-label="Floor plan page" type="number" min={1} max={planPreview.data?.page_count} step={1}
                            value={planPage} disabled={createLayout.isPending} onChange={(e) => setPlanPage(Number(e.target.value))} className="mt-1 h-8" />
                        </label>
                        <label>Clockwise rotation
                          <select aria-label="Floor plan rotation" value={planRotation} disabled={createLayout.isPending}
                            onChange={(e) => setPlanRotation(Number(e.target.value))} className="mt-1 h-8 w-full rounded border bg-background px-2">
                            {[0, 90, 180, 270].map((angle) => <option key={angle} value={angle}>{angle}°</option>)}
                          </select>
                        </label>
                      </div>
                      {planPreview.isFetching && <p className="text-xs text-muted-foreground" role="status">Rendering preview…</p>}
                      {planPreview.isError && <p role="alert" className="text-xs text-destructive">{planPreview.error.message}</p>}
                      {planPreview.data && <img src={planPreview.data.image}
                        alt={`Floor plan page ${planPreview.data.page_number}, rotated ${planPreview.data.rotation} degrees clockwise`}
                        className="max-h-48 w-full rounded border bg-white object-contain" />}
                      <p className="text-xs text-muted-foreground">Confirm the selected page and orientation before creating the layout. Preview uses no vision model.</p>
                    </div>}
                    <div className="flex gap-1.5 text-xs">
                      {([["auto", "Vision model, geometry fallback"], ["classic", "Geometry only (offline)"]] as const).map(([id, label]) => (
                        <button key={id} type="button" onClick={() => setPlanReader(id)}
                          className={cn("flex-1 rounded-lg border px-2 py-1.5", planReader === id ? "border-primary bg-primary/10 font-medium" : "text-muted-foreground hover:border-foreground/20")}>
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </RadioGroup>
          </div>

          {createLayout.isError && (
            <p className="text-xs text-destructive">
              {createLayout.error instanceof Error
                ? createLayout.error.message
                : "Failed to create layout."}
            </p>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={createLayout.isPending}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              data-testid="add-layout-submit"
              disabled={!canSubmit}
              className={cn(createLayout.isPending && "opacity-80")}
            >
              {createLayout.isPending ? "Adding..." : approach === "building" ? `Add ${floors.length} floors` : "Add layout"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
