import { mutationOptions } from "@tanstack/react-query";
import {
  previewCaptureBatch,
  saveCaptureBatch,
  type CaptureBatchRequest,
  type CaptureBatchSave,
} from "@/shared/api/captureBatch";
export const captureBatchPreview = (pid: string) =>
  mutationOptions({
    mutationFn: (req: CaptureBatchRequest) => previewCaptureBatch(pid, req),
  });
export const captureBatchSave = (pid: string) =>
  mutationOptions({
    mutationFn: (req: CaptureBatchSave) => saveCaptureBatch(pid, req),
  });
