// Before a vision run with the "chart + 3D photo" shelf view: photograph the layout's shelf faces that have
// no stored photo yet (in this browser, with Realistic mode's renderer) and upload them. Faces whose racks
// did not change since an earlier run are reused, so later runs start at once.

import * as api from "@/shared/api/client";

export async function photographShelves(
  projectId: string,
  setupId: string,
  onProgress: (done: number, total: number) => void,
  signal?: AbortSignal,
): Promise<number> {
  const status = await api.getShelfViews(projectId, setupId, signal);
  const missing = status.faces.filter((face) => !face.ready);
  onProgress(0, missing.length);
  if (!missing.length) return 0;
  // three.js and the realistic store builders load only when a photo is needed.
  const { renderShelfFaces } = await import("@/features/store-viewer/realistic/shelfSnapshots");
  let done = 0;
  await renderShelfFaces(
    status.store,
    missing.map((face) => ({ rackId: face.rack_id, face: face.face })),
    status.currency,
    async (_request, shot, index) => {
      const face = missing[index]!;
      await api.putShelfView(projectId, setupId, face.key, { rack_id: face.rack_id, face: face.face, image: shot.image, boxes: shot.boxes }, signal);
      done += 1;
      onProgress(done, missing.length);
    },
    signal,
  );
  if (signal?.aborted) throw new DOMException("Photographing the shelves was cancelled.", "AbortError");
  return done;
}
