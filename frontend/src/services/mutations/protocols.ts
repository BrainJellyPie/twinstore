import { mutationOptions, type QueryClient } from "@tanstack/react-query";
import { amendProtocol, createProtocol, exportProtocol, type AmendProtocol, type CreateProtocol } from "@/shared/api/protocols";
import { protocolKeys } from "@/services/queries/protocols";

// Never publish delayed save responses into a newer editor. The submitting, still-mounted
// editor explicitly reloads its saved history; abandoned requests only refresh the list.
export const protocolCreate = (pid: string, qc: QueryClient) => mutationOptions({ mutationFn: (req: CreateProtocol) => createProtocol(pid, req), onSuccess: () => qc.invalidateQueries({ queryKey: protocolKeys.list(pid) }) });
export const protocolAmend = (pid: string, id: string, qc: QueryClient) => mutationOptions({ mutationFn: (req: AmendProtocol) => amendProtocol(pid, id, req), onSuccess: () => qc.invalidateQueries({ queryKey: protocolKeys.list(pid) }) });
export const protocolExport = (pid: string, id: string) => mutationOptions({ mutationFn: (req: { head: string; format: "json" | "csv" }) => exportProtocol(pid, id, req.head, req.format) });
