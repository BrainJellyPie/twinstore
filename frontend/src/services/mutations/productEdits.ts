import { mutationOptions } from "@tanstack/react-query";
import { previewProductEdits, saveProductEdits, type ProductEditsRequest, type ProductEditsSave } from "@/shared/api/productEdits";
export const productPreview = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: ProductEditsRequest) => previewProductEdits(pid, sid, body), retry: false });
export const productSave = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: ProductEditsSave) => saveProductEdits(pid, sid, body), retry: false });
