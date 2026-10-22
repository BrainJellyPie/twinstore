import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { getRackCopyOptions } from "@/shared/api/rackCopy";
export const rackCopyOptions = (pid: string, sid: string, source: string) => queryOptions({
  queryKey: ["rack-copy", pid, sid, source], queryFn: ({ signal }) => getRackCopyOptions(pid, sid, source, signal),
  placeholderData: keepPreviousData, refetchOnWindowFocus: false, refetchOnReconnect: false, retry: false, gcTime: 0,
});
