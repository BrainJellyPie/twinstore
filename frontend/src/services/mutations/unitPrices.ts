import { mutationOptions } from "@tanstack/react-query";
import { exportUnitPrices, previewUnitPrices, unitPriceTemplate, type PriceExport, type PriceUpload } from "@/shared/api/unitPrices";

export const unitPricePreview = (pid: string) => mutationOptions({ mutationFn: (req: PriceUpload) => previewUnitPrices(pid, req) });
export const unitPriceExport = (pid: string) => mutationOptions({ mutationFn: (req: PriceExport) => exportUnitPrices(pid, req) });
export const unitPriceTemplateDownload = (pid: string) => mutationOptions({ mutationFn: () => unitPriceTemplate(pid) });
