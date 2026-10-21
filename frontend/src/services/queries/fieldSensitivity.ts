import { queryOptions } from "@tanstack/react-query";

import { getPilotSensitivity, sensitivityKey } from "@/shared/api/fieldSensitivity";

export const pilotSensitivityQuery = (projectId: string, pilotId: string, revision: number, enabled: boolean) => queryOptions({
  queryKey: sensitivityKey(projectId, pilotId, revision),
  queryFn: ({ signal }) => getPilotSensitivity(projectId, pilotId, revision, signal),
  enabled,
  retry: false,
});
