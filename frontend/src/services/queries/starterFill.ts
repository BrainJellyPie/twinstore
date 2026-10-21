import { queryOptions } from "@tanstack/react-query";
import { getStarterCatalog } from "@/shared/api/starterFill";
export const starterCatalog = (pid: string, sid: string) => queryOptions({
  queryKey: ["starter-fill", pid, sid], queryFn: ({ signal }) => getStarterCatalog(pid, sid, signal),
  refetchOnWindowFocus: false, refetchOnReconnect: false, retry: false, gcTime: 0,
});
