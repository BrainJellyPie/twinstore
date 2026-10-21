import { queryOptions } from "@tanstack/react-query";
import { getFactorialSource } from "@/shared/api/factorial";

export const factorialSourceQuery = (pid: string, eid: string, enabled: boolean) => queryOptions({
  queryKey: ["factorial-source", pid, eid], queryFn: ({ signal }) => getFactorialSource(pid, eid, signal), enabled, retry: false,
});
