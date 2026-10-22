import { mutationOptions } from "@tanstack/react-query";
import { previewStarterFill, saveStarterFill, type StarterRequest, type StarterSave } from "@/shared/api/starterFill";
export const starterPreview = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: StarterRequest) => previewStarterFill(pid, sid, body), retry: false });
export const starterSave = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: StarterSave) => saveStarterFill(pid, sid, body), retry: false });
