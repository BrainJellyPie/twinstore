import { mutationOptions } from "@tanstack/react-query";

import { exportInventory, inventoryTemplate, previewInventory, type InventoryUpload } from "@/shared/api/inventoryReview";

export const inventoryPreview = (pid: string) => mutationOptions({ mutationFn: (req: InventoryUpload) => previewInventory(pid, req) });
export const inventoryExport = (pid: string) => mutationOptions({ mutationFn: (req: InventoryUpload) => exportInventory(pid, req) });
export const inventoryTemplateDownload = (pid: string) => mutationOptions({ mutationFn: () => inventoryTemplate(pid) });
