import * as api from "@/shared/api/client";
// The queue owns its poll lifetime; accepted jobs keep running when the browser leaves.
export const captureUploadStatus = (
  pid: string,
  cid: string,
  signal: AbortSignal,
) => api.getCapture(pid, cid, signal);
