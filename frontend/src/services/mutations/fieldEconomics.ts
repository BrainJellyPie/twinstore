import { mutationOptions } from "@tanstack/react-query";

import { exportPilotEconomics, previewPilotEconomics, type PilotEconomicsRequest } from "@/shared/api/fieldEconomics";

export const pilotEconomicsPreview = (pid: string, id: string) => mutationOptions({
  mutationFn: (request: PilotEconomicsRequest) => previewPilotEconomics(pid, id, request),
});
export const pilotEconomicsExport = (pid: string, id: string) => mutationOptions({
  mutationFn: (request: PilotEconomicsRequest) => exportPilotEconomics(pid, id, request),
});
