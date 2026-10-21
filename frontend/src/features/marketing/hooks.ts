import { useQuery } from "@tanstack/react-query";

import * as api from "@/shared/api/client";
import { marketingKeys } from "@/shared/api/marketing";

export function usePackages(projectId: string) {
  return useQuery({ queryKey: marketingKeys.packages(projectId), queryFn: ({ signal }) => api.listPackages(projectId, signal) });
}
