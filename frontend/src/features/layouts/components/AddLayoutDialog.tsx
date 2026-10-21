// Approach radio:
//   - "Import from..." (default): clone an existing layout as parent (API mode=racks_and_items).
//   - "Build from scratch": create an empty setup (API mode=empty).
// The "racks only" option exists in the API (mode=racks) but is intentionally not
// exposed in this dialog.
//
// On success, useCreateLayout's onSuccess switches selectedSetupId to the new layout
// and this component closes via onOpenChange(false).

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { useCreateLayout } from "../hooks/useCreateLayout";
import { BuildingPicker } from "./BuildingPicker";
import { TemplatePicker } from "./TemplatePicker";
import { DEFAULT_TEMPLATE_CHOICE, buildingPreset, choiceFromGeneration, savedBuildingFloors, validBuildingFloors, validTemplateChoice, type TemplateChoice } from "../templateOptions";
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
  isCurrentProject?: () => boolean;
}

function resolveDefaultParent(parentSetupId: string, layouts: Layout[]): string {
  if (layouts.some(layout => layout.id === parentSetupId)) return parentSetupId;
  return layouts[0]?.id ?? "";
}

export function AddLayoutDialog({
  open,
  onOpenChange,
  projectId,
  parentSetupId,
  layouts,
  defaultCurrency = "USD",
  isCurrentProject,
}: AddLayoutDialogProps) {
  const { t } = useI18n();
  const createLayout = useCreateLayout({ active: open, projectId, canSelect: isCurrentProject });
  const creating = useRef(false);
  const planInput = useRef<HTMLInputElement>(null);
  const choosePlan = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  const [name, setName] = useState<string>(() => t("layoutDefaultName", { number: layouts.length + 1 }));
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

  // Keep pending and failed requests attached to their inputs when reopening.
  useEffect(() => {
    if (open && !creating.current && !createLayout.isError) {
      setName(t("layoutDefaultName", { number: layouts.length + 1 }));
      setApproach("import");
      setPlanFile(null);
      setPlanPage(1);
      setPlanRotation(0);
      setSelectedParentId(resolveDefaultParent(parentSetupId, layouts));
      setTemplate((current) => ({ ...current, currency: defaultCurrency, sourceSetupId: undefined }));
      setFloors((current) => current.map((floor) => ({ ...floor, choice: { ...floor.choice, currency: defaultCurrency, sourceSetupId: undefined } })));
      createLayout.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const trimmed = name.trim();
  const sourceLayout = layouts.find((layout) => layout.id === parentSetupId);
  const savedFloors = savedBuildingFloors(layouts, sourceLayout);
  const buildingSources = sourceLayout?.building
    ? layouts.filter((layout) => layout.building?.id === sourceLayout.building!.id && layout.generation) : [];
  const ownsSource = (id: string | undefined) => !id || layouts.some(layout => layout.id === id);
  const missingSource = approach === "import" ? !selectedParentId || !ownsSource(selectedParentId)
    : approach === "template" ? !ownsSource(template.sourceSetupId)
    : approach === "building" && floors.some(floor => !ownsSource(floor.choice.sourceSetupId));
  const canSubmit =
    trimmed.length > 0 &&
    !missingSource &&
    !createLayout.isPending &&
    (approach !== "import" || selectedParentId.length > 0) &&
    (approach !== "plan" || (planFile !== null && planPage >= 1 && Number.isInteger(planPage) && planPreview.isSuccess)) &&
    (approach !== "template" || validTemplateChoice(template)) &&
    (approach !== "building" || (trimmed.length <= 160 && validBuildingFloors(floors)));

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || creating.current) return;
    creating.current = true;
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
        onSettled: () => { creating.current = false; },
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("flex max-h-[90dvh] min-w-0 flex-col overflow-hidden p-4 [overflow-wrap:anywhere] sm:p-7", (approach === "template" || approach === "building") ? "sm:max-w-[760px]" : "sm:max-w-[420px]")}
        onOpenAutoFocus={() => {
          const active = document.activeElement;
          opener.current = active instanceof HTMLElement && active !== document.body ? active : null;
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          const target = opener.current;
          opener.current = null;
          if (target?.isConnected && document.activeElement === document.body && isCurrentProject?.() !== false &&
            (typeof target.checkVisibility !== "function" || target.checkVisibility())) target.focus();
        }}>
        <DialogHeader>
          <DialogTitle>{t("addLayoutTitle")}</DialogTitle>
          <DialogDescription className="sr-only">{t("addLayoutDescription")}</DialogDescription>
        </DialogHeader>

        {createLayout.isPending && <p role="status" className="shrink-0 rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground">{t("layoutCreationBackgroundHint")}</p>}

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col gap-4">
          <div className="-mx-1 min-h-0 min-w-0 flex-1 overflow-y-auto px-1" data-testid="add-layout-scroll-area">
          <fieldset disabled={createLayout.isPending} className="m-0 min-w-0 space-y-4 border-0 p-0">
          <div className="space-y-1.5">
            <label className={labelClass} htmlFor="add-layout-name">
              {t(approach === "building" ? "buildingNameLabel" : "layoutNameLabel")}
            </label>
            <Input
              id="add-layout-name"
              data-testid="add-layout-name-input"
              value={name}
              maxLength={approach === "building" ? 160 : 300}
              placeholder={t("layoutNameExample")}
              disabled={createLayout.isPending}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          {missingSource && <div role="alert" className="space-y-2 rounded-lg border border-destructive/30 p-3 text-sm [overflow-wrap:anywhere]">
            <p>{t(approach === "import" ? "importSourceUnavailable" : "savedSourceUnavailable")}</p>
            {approach !== "import" && <button type="button" disabled={createLayout.isPending} className="rounded-lg border px-3 py-2 font-medium hover:bg-muted disabled:opacity-50"
              onClick={() => {
                if (approach === "template") setTemplate(current => ({ ...current, sourceSetupId: undefined }));
                else setFloors(current => current.map(floor => ({ ...floor, choice: { ...floor.choice, sourceSetupId: undefined } })));
              }}>{t("unlinkSavedSources")}</button>}
          </div>}

          <div className="space-y-2">
            <div role="radiogroup" className="grid gap-3" aria-label={t("layoutCreationApproach")}
              onKeyDown={(event) => {
                if (event.key === "Enter" && event.target instanceof HTMLInputElement &&
                  (event.target.type === "radio" || (!event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229))) event.preventDefault();
              }}>
              <div className="space-y-2">
                <label
                  className="flex items-center gap-2 text-sm"
                  htmlFor="add-layout-approach-import"
                >
                  <input type="radio"
                    id="add-layout-approach-import"
                    data-testid="add-layout-approach-import"
                    value="import" name={`layout-approach-${previewScope}`} checked={approach === "import"} onChange={() => setApproach("import")}
                    disabled={createLayout.isPending} className="size-4 shrink-0 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  />
                  {t("importLayoutFrom")}
                </label>
                {approach === "import" && (
                  <Select
                    value={ownsSource(selectedParentId) ? selectedParentId : ""}
                    onValueChange={setSelectedParentId}
                    disabled={createLayout.isPending}
                  >
                    <SelectTrigger
                      aria-label={t("sourceLayoutLabel")}
                      id="add-layout-parent"
                      data-testid="add-layout-parent-trigger"
                      className="w-full"
                    >
                      <SelectValue placeholder={t("sourceLayoutLabel")} />
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
                <input type="radio"
                  id="add-layout-approach-empty"
                  data-testid="add-layout-approach-empty"
                  value="empty" name={`layout-approach-${previewScope}`} checked={approach === "empty"} onChange={() => setApproach("empty")}
                  disabled={createLayout.isPending} className="size-4 shrink-0 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                />
                {t("buildLayoutFromScratch")}
              </label>

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-template">
                  <input type="radio"
                    id="add-layout-approach-template"
                    value="template" name={`layout-approach-${previewScope}`} checked={approach === "template"} onChange={() => setApproach("template")}
                    disabled={createLayout.isPending} className="size-4 shrink-0 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  />
                  {t("generateLayoutFromTemplate")}
                </label>
                {approach === "template" && <>
                  {sourceLayout?.generation && <div className="space-y-1 rounded-md border p-3 text-xs">
                    <button type="button" className="font-medium text-primary underline" onClick={() => setTemplate(choiceFromGeneration(sourceLayout.generation!, sourceLayout.id))}>
                      {t("reuseLayoutOptions", { name: sourceLayout.name })}
                    </button>
                    <p className="text-muted-foreground">{t("reuseLayoutHint")}</p>
                    {template.sourceSetupId === sourceLayout.id && <p role="status">{t("layoutSourceLinkHint", { name: sourceLayout.name })}</p>}
                  </div>}
                  <TemplatePicker value={template} budgetCurrency={defaultCurrency} onChange={setTemplate} defaultCustomizationOpen={false} />
                </>}
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-building">
                  <input type="radio" id="add-layout-approach-building" value="building" name={`layout-approach-${previewScope}`} checked={approach === "building"} onChange={() => setApproach("building")} disabled={createLayout.isPending} className="size-4 shrink-0 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary" />
                  {t("multiFloorLayout")}
                </label>
                {approach === "building" && <>
                  {sourceLayout?.building && <div className="space-y-1 rounded-md border p-3 text-xs">
                    <button type="button" disabled={!savedFloors} className="font-medium text-primary underline disabled:opacity-40"
                      onClick={() => {
                        if (!savedFloors) return;
                        setFloors(savedFloors);
                        setName(t("buildingAlternativeName", { name: sourceLayout.building!.name.slice(0, 148) }));
                      }}>{t("reuseBuildingOptions", { name: sourceLayout.building.name })}</button>
                    <p className="text-muted-foreground">{t("reuseBuildingHint")}</p>
                    <p className="text-muted-foreground">{t("buildingRegenerationHint")}</p>
                    {!savedFloors && <p>{t("buildingSettingsRequired")}</p>}
                  </div>}
                  <BuildingPicker floors={floors} defaultCurrency={defaultCurrency} onChange={setFloors} sourceLayouts={buildingSources} />
                </>}
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm" htmlFor="add-layout-approach-plan">
                  <input type="radio" id="add-layout-approach-plan" value="plan" name={`layout-approach-${previewScope}`} checked={approach === "plan"} onChange={() => setApproach("plan")} disabled={createLayout.isPending} className="size-4 shrink-0 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary" />
                  {t("layoutFromFloorPlan")}
                </label>
                {approach === "plan" && (
                  <div className="space-y-2 rounded-xl border bg-foreground/[0.02] p-3">
                    <div className="flex min-w-0 flex-col items-center gap-1.5 rounded-xl border border-dashed border-foreground/15 px-3 py-5 text-center text-sm">
                      <button ref={choosePlan} type="button" disabled={createLayout.isPending} onClick={() => planInput.current?.click()}
                        className="max-w-full rounded-lg border px-3 py-2 font-medium transition-colors hover:border-primary focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-50">{t("choosePlanImage")}</button>
                      {planFile && <>
                        <p role="status" className="max-w-full [overflow-wrap:anywhere]">{planFile.name}</p>
                        <button type="button" disabled={createLayout.isPending} onClick={() => {
                          setPlanFile(null); setPlanFileVersion(version => version + 1); setPlanPage(1); setPlanRotation(0); choosePlan.current?.focus();
                        }} className="max-w-full rounded-lg border px-3 py-2 text-xs hover:bg-muted disabled:opacity-50">{t("removeSelectedFile")}</button>
                      </>}
                      <span className="text-xs text-muted-foreground">{t("floorPlanDrawingHint")}</span>
                      <input ref={planInput} type="file" accept="image/png,image/jpeg,image/webp,application/pdf" className="hidden" disabled={createLayout.isPending}
                        aria-label={t("chooseFloorPlanFile")} onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setPlanFile(file);
                          setPlanFileVersion((version) => version + 1);
                          setPlanPage(1);
                          setPlanRotation(0);
                          e.target.value = "";
                        }} />
                    </div>
                    {planFile && <div className="space-y-2">
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <label>{planPreview.data ? t("floorPlanPageOf", { count: planPreview.data.page_count }) : t("floorPlanPageLabel")}
                          <Input aria-label={t("floorPlanPageInput")} type="number" min={1} max={planPreview.data?.page_count} step={1}
                            value={planPage} disabled={createLayout.isPending} onChange={(e) => setPlanPage(Number(e.target.value))} className="mt-1 h-8" />
                        </label>
                        <label>{t("floorPlanRotationLabel")}
                          <select aria-label={t("floorPlanRotationInput")} value={planRotation} disabled={createLayout.isPending}
                            onChange={(e) => setPlanRotation(Number(e.target.value))} className="mt-1 h-8 w-full rounded border bg-background px-2">
                            {[0, 90, 180, 270].map((angle) => <option key={angle} value={angle}>{angle}°</option>)}
                          </select>
                        </label>
                      </div>
                      {planPreview.isFetching && <p className="text-xs text-muted-foreground" role="status">{t("floorPlanRendering")}</p>}
                      {planPreview.isError && <div className="space-y-2 text-xs">
                        <p role="alert" className="text-destructive">{t("floorPlanPreviewFailed")} {planPreview.error.message}</p>
                        <button type="button" disabled={planPreview.isFetching || createLayout.isPending} onClick={() => { void planPreview.refetch(); }}
                          className="rounded-lg border px-3 py-2 hover:bg-muted disabled:opacity-50">{t("tryAgain")}</button>
                      </div>}
                      {planPreview.data && <img src={planPreview.data.image}
                        alt={t("floorPlanPreviewAlt", { page: planPreview.data.page_number, rotation: planPreview.data.rotation })}
                        className="max-h-48 w-full rounded border bg-white object-contain" />}
                      <p className="text-xs text-muted-foreground">{t("floorPlanPreviewHint")}</p>
                    </div>}
                    <div className="flex gap-1.5 text-xs">
                      {([["auto", "visionPlanReader"], ["classic", "geometryPlanReader"]] as const).map(([id, label]) => (
                        <button key={id} type="button" aria-pressed={planReader === id} disabled={createLayout.isPending} onClick={() => setPlanReader(id)}
                          className={cn("flex-1 rounded-lg border px-2 py-1.5", planReader === id ? "border-primary bg-primary/10 font-medium" : "text-muted-foreground hover:border-foreground/20")}>
                          {t(label)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          </fieldset>
          </div>

          {createLayout.isError && (
            <p role="alert" className="max-h-24 shrink-0 overflow-y-auto rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
              <span className="block font-medium">{t("createLayoutFailed")}</span>
              {createLayout.error instanceof Error && createLayout.error.message && <span className="mt-1 block">{createLayout.error.message}</span>}
            </p>
          )}

          <DialogFooter className="-mx-4 -mb-4 shrink-0 px-4 sm:-mx-7 sm:-mb-7 sm:px-7">
            <Button
              type="button"
              variant="outline"
              disabled={createLayout.isPending}
              onClick={() => onOpenChange(false)}
            >
              {t("cancel")}
            </Button>
            <Button
              type="submit"
              variant="default"
              data-testid="add-layout-submit"
              disabled={!canSubmit}
              className={cn(createLayout.isPending && "opacity-80")}
            >
              {createLayout.isPending ? t("addingLayout") : approach === "building" ? t(floors.length === 1 ? "addOneBuildingFloor" : "addBuildingFloors", { count: floors.length }) : t("addLayoutTitle")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
