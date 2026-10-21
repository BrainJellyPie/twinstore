import { queryOptions } from "@tanstack/react-query";
import { getProtocol, listProtocols } from "@/shared/api/protocols";

export const protocolKeys = { list: (pid: string) => ["protocols", pid] as const, detail: (pid: string, id: string) => ["protocol", pid, id] as const };
export const protocolsQuery = (pid: string) => queryOptions({ queryKey: protocolKeys.list(pid), queryFn: ({ signal }) => listProtocols(pid, signal), retry: false });
export const protocolQuery = (pid: string, id: string) => queryOptions({ queryKey: protocolKeys.detail(pid, id), queryFn: ({ signal }) => getProtocol(pid, id, signal), retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false });
