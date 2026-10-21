import { useQuery } from "@tanstack/react-query";
import { getSetups, type SetupSummary } from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";

// SetupSummary mirrors the API response shape; Layout is the UI-friendly view
// (snake_case → camelCase, only the fields the UI needs).
export interface Layout {
  id: string;
  name: string;
  parentId: string | null;
  status: string;
  createdAt: string;
  building?: SetupSummary["building"];
  generation?: SetupSummary["generation"];
}

function toLayout(s: SetupSummary): Layout {
  return {
    id: s.id,
    name: s.name,
    parentId: s.parentId,
    status: s.status,
    createdAt: s.created_at,
    building: s.building,
    generation: s.generation,
  };
}

export function useLayouts(projectId: string) {
  return useQuery({
    queryKey: queryKeys.setups(projectId),
    queryFn: ({ signal }) => getSetups(projectId, signal),
    select: (setups) =>
      setups.map(toLayout).sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
  });
}
