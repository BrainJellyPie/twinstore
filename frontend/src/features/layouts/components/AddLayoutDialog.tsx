// Approach radio:
//   - "Import from..." (default): clone an existing layout as parent (API mode=racks_and_items).
//   - "Build from scratch": create an empty setup (API mode=empty).
// The "racks only" option exists in the API (mode=racks) but is intentionally not
// exposed in this dialog.
//
// On success, useCreateLayout's onSuccess switches selectedSetupId to the new layout
// and this component closes via onOpenChange(false).

import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
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
import { DEFAULT_TEMPLATE_CHOICE, buildingPreset, validBuildingFloors, validTemplateChoice, type TemplateChoice } from "../templateOptions";
import type { Layout } from "../hooks/useLayouts";

type Approach = "import" | "empty" | "template" | "plan" | "building";

const labelClass = "text-sm font-medium";

export interface AddLayoutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  parentSetupId: string;
  layouts: Layout[];
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
}: AddLayoutDialogProps) {
  const createLayout = useCreateLayout();

  const [name, setName] = useState<string>(() => `layout ${layouts.length + 1}`);
  const [approach, setApproach] = useState<Approach>("import");
  const [selectedParentId, setSelectedParentId] = useState<string>(() =>
    resolveDefaultParent(parentSetupId, layouts),
  );
  const [template, setTemplate] = useState<TemplateChoice>(DEFAULT_TEMPLATE_CHOICE);
  const [floors, setFloors] = useState(() => buildingPreset("department"));
  const [planFile, setPlanFile] = useState<File | null>(null);
  const [planReader, setPlanReader] = useState<"auto" | "classic">("auto");

  // Restore defaults on each open; also reset the prior mutation's error state.
  useEffect(() => {
    if (open) {
      setName(`layout ${layouts.length + 1}`);
      setApproach("import");
      setPlanFile(null);
      setSelectedParentId(resolveDefaultParent(parentSetupId, layouts));
      createLayout.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const trimmed = name.trim();
  const canSubmit =
    trimmed.length > 0 &&
    !createLayout.isPending &&
    (approach !== "import" || selectedParentId.length > 0) &&
    (approach !== "plan" || planFile !== null) &&
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
                ? { kind: "plan", file: planFile, reader: planReader }
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
                {approach === "template" && <TemplatePicker value={template} onChange={setTemplate} />}
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-building">
                  <RadioGroupItem id="add-layout-approach-building" value="building" disabled={createLayout.isPending} />
                  Multi-floor store
                </label>
                {approach === "building" && <BuildingPicker floors={floors} onChange={setFloors} />}
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
                      <input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" className="hidden"
                        onChange={(e) => setPlanFile(e.target.files?.[0] ?? null)} />
                    </label>
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
