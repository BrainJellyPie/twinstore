import { mutationOptions } from "@tanstack/react-query";
import { previewRackCopy, saveRackCopy, type RackCopyRequest, type RackCopySave } from "@/shared/api/rackCopy";
export const rackCopyPreview = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: RackCopyRequest) => previewRackCopy(pid, sid, body), retry: false });
export const rackCopySave = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: RackCopySave) => saveRackCopy(pid, sid, body), retry: false });
