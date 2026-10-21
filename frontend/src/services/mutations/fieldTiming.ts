import { mutationOptions } from "@tanstack/react-query";

import { exportTiming, previewTiming, timingTemplate, type TimingUpload } from "@/shared/api/fieldTiming";

export const pilotTimingPreview = (pid: string, id: string) => mutationOptions({
  mutationFn: (request: TimingUpload) => previewTiming(pid, id, request),
});
export const pilotTimingExport = (pid: string, id: string) => mutationOptions({
  mutationFn: (request: TimingUpload) => exportTiming(pid, id, request),
});
export const pilotTimingTemplate = (pid: string, id: string) => mutationOptions({
  mutationFn: (revision: number) => timingTemplate(pid, id, revision),
});
