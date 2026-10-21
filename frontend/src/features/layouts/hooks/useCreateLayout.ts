import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef } from "react";
import { createSetup, generateBuilding, generateLayout, importFloorPlan, type SetupSummary, type SetupSummaryShort } from "@/shared/api/client";
import { templateRequest, type BuildingFloorChoice, type TemplateChoice } from "../templateOptions";
import { queryKeys } from "@/shared/queries/keys";
import { useSimulationStore } from "@/stores/simulationStore";

// "import" clones from a parent setup; "empty" creates a blank setup; "template" generates a
// complete store from a retail-format template; "plan" reads a floor plan image into a layout.
type CreateLayoutSource =
  | { kind: "import"; parentSetupId: string }
  | { kind: "empty" }
  | { kind: "building"; floors: BuildingFloorChoice[] }
  | ({ kind: "template" } & TemplateChoice)
  | { kind: "plan"; file: File; reader: "auto" | "classic"; pageNumber: number; rotation: number };

interface Params {
  projectId: string;
  name: string;
  source: CreateLayoutSource;
}

interface ActivationOptions {
  active?: boolean;
  projectId?: string;
  canSelect?: () => boolean;
}

export function useCreateLayout({ active = true, projectId, canSelect }: ActivationOptions = {}) {
  const qc = useQueryClient();
  const setSelected = useSimulationStore((s) => s.setSelectedSetupId);
  const mounted = useRef(false);
  const owner = useRef({ active, projectId, canSelect, version: 0 });
  useLayoutEffect(() => {
    const previous = owner.current;
    const changed = previous.active !== active || previous.projectId !== projectId;
    owner.current = { active, projectId, canSelect, version: changed ? previous.version + 1 : previous.version };
  }, [active, projectId, canSelect]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  return useMutation<SetupSummaryShort, Error, Params, { version: number; selectedId: string | null }>({
    onMutate: () => ({ version: owner.current.version, selectedId: useSimulationStore.getState().selectedSetupId }),
    mutationFn: ({ projectId, name, source }) =>
      source.kind === "building"
        ? generateBuilding(projectId, { name, floors: source.floors.map((f) => ({ label: f.label, layout: templateRequest(f.choice) })) }).then((result) => result.setups[0]!)
        : source.kind === "plan"
        ? importFloorPlan(projectId, source.file, { reader: source.reader, name, pageNumber: source.pageNumber, rotation: source.rotation }).then((r) => r.setup)
        : source.kind === "template"
        ? generateLayout(projectId, {
            ...templateRequest(source), name,
          })
        : createSetup(projectId, {
            mode: source.kind === "import" ? "racks_and_items" : "empty",
            source_setup_id: source.kind === "import" ? source.parentSetupId : null,
            name,
          }),
    onSuccess: async (newSetup, vars, context) => {
      // A list request started before creation must not erase the new selection.
      await qc.cancelQueries({ queryKey: queryKeys.setups(vars.projectId) });
      qc.setQueryData<SetupSummary[]>(queryKeys.setups(vars.projectId), (current = []) =>
        [...current.filter((setup) => setup.id !== newSetup.id), newSetup],
      );
      qc.invalidateQueries({ queryKey: queryKeys.setups(vars.projectId) });
      qc.invalidateQueries({ queryKey: queryKeys.project(vars.projectId) });
      const current = owner.current;
      if (mounted.current && context && current.active && context.version === current.version &&
        (current.projectId === undefined || current.projectId === vars.projectId) &&
        useSimulationStore.getState().selectedSetupId === context.selectedId && current.canSelect?.() !== false) setSelected(newSetup.id);
    },
  });
}
