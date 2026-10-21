import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSetup, generateLayout, importFloorPlan, type SetupSummaryShort } from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";

// "import" clones from a parent setup; "empty" creates a blank setup; "template" generates a
// complete store from a retail-format template; "plan" reads a floor plan image into a layout.
type CreateLayoutSource =
  | { kind: "import"; parentSetupId: string }
  | { kind: "empty" }
  | { kind: "template"; templateId: string; seed: number; currency: string; style: "aisles" | "loop" | null }
  | { kind: "plan"; file: File; reader: "auto" | "classic"; pageNumber: number; rotation: number };

interface Params {
  projectId: string;
  name: string;
  source: CreateLayoutSource;
}

export function useCreateLayout() {
  const qc = useQueryClient();
  const setSelected = useSimulationStore((s) => s.setSelectedSetupId);

  return useMutation<SetupSummaryShort, Error, Params>({
    mutationFn: ({ projectId, name, source }) =>
      source.kind === "plan"
        ? importFloorPlan(projectId, source.file, { reader: source.reader, name, pageNumber: source.pageNumber, rotation: source.rotation }).then((r) => r.setup)
        : source.kind === "template"
        ? generateLayout(projectId, {
            template_id: source.templateId, seed: source.seed, currency: source.currency, style: source.style, name,
          })
        : createSetup(projectId, {
            mode: source.kind === "import" ? "racks_and_items" : "empty",
            source_setup_id: source.kind === "import" ? source.parentSetupId : null,
            name,
          }),
    onSuccess: (newSetup, vars) => {
      qc.invalidateQueries({ queryKey: queryKeys.setups(vars.projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.project(vars.projectId) });
      setSelected(newSetup.id);
    },
  });
}
