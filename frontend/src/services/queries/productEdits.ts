import { queryOptions } from "@tanstack/react-query";
import { getProductCatalog } from "@/shared/api/productEdits";
export const productCatalog = (pid: string, sid: string) => queryOptions({
  queryKey: ["product-editor", pid, sid],
  queryFn: ({ signal }) => getProductCatalog(pid, sid, signal),
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  gcTime: 0,
  retry: false,
});
