import { mutationOptions } from "@tanstack/react-query";
import { exportPriceChecks, previewPriceChecks, priceCheckTemplate, type CheckExport, type CheckUpload } from "@/shared/api/priceChecks";

export const priceCheckPreview = (pid: string) => mutationOptions({ mutationFn: (req: CheckUpload) => previewPriceChecks(pid, req) });
export const priceCheckExport = (pid: string) => mutationOptions({ mutationFn: (req: CheckExport) => exportPriceChecks(pid, req) });
export const priceCheckTemplateDownload = (pid: string) => mutationOptions({ mutationFn: () => priceCheckTemplate(pid) });
