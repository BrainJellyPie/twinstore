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
import { TemplatePicker, type TemplateChoice } from "./TemplatePicker";
import type { Layout } from "../hooks/useLayouts";

type Approach = "import" | "empty" | "template";

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
  const [template, setTemplate] = useState<TemplateChoice>({ templateId: "urban_cvs", seed: 0, currency: "USD", style: null });

  // Restore defaults on each open; also reset the prior mutation's error state.
  useEffect(() => {
    if (open) {
      setName(`layout ${layouts.length + 1}`);
      setApproach("import");
      setSelectedParentId(resolveDefaultParent(parentSetupId, layouts));
      createLayout.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const trimmed = name.trim();
  const canSubmit =
    trimmed.length > 0 &&
    !createLayout.isPending &&
    (approach !== "import" || selectedParentId.length > 0);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    createLayout.mutate(
      {
        projectId,
        name: trimmed,
        source:
          approach === "import"
            ? { kind: "import", parentSetupId: selectedParentId }
            : approach === "template"
              ? { kind: "template", ...template }
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
      <DialogContent className={approach === "template" ? "sm:max-w-[600px]" : "sm:max-w-[420px]"}>
        <DialogHeader>
          <DialogTitle>Add layout</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className={labelClass} htmlFor="add-layout-name">
              Layout name
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
              {createLayout.isPending ? "Adding..." : "Add layout"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
