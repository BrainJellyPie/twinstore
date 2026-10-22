import { queryOptions } from "@tanstack/react-query";
import { getLibraryPhotos } from "@/shared/api/libraryPhotos";
export const libraryPhotosOptions = (pid: string, sid: string) => queryOptions({
  queryKey: ["library-photos", pid, sid], queryFn: ({ signal }) => getLibraryPhotos(pid, sid, signal),
  refetchOnWindowFocus: false, refetchOnReconnect: false, retry: false, gcTime: 0,
});
