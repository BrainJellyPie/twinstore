import { mutationOptions } from "@tanstack/react-query";
import * as api from "@/shared/api/client";
export type CaptureUploadOptions = Parameters<typeof api.createCapture>[2];
export const captureUpload = (pid: string) =>
  mutationOptions({
    mutationFn: ({
      file,
      options,
      signal,
    }: {
      file: File;
      options: CaptureUploadOptions;
      signal: AbortSignal;
    }) => api.createCapture(pid, file, options, signal),
  });
