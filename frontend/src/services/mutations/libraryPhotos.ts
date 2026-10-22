import { mutationOptions } from "@tanstack/react-query";
import { previewLibraryPhotos, saveLibraryPhotos, type PhotoRequest, type PhotoSave } from "@/shared/api/libraryPhotos";
export const libraryPhotosPreview = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: PhotoRequest) => previewLibraryPhotos(pid, sid, body), retry: false });
export const libraryPhotosSave = (pid: string, sid: string) => mutationOptions({ mutationFn: (body: PhotoSave) => saveLibraryPhotos(pid, sid, body), retry: false });
