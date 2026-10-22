import { afterEach, expect, it, vi } from "vitest";
import * as api from "@/shared/api/client";
import { renderShelfFaces } from "@/features/store-viewer/realistic/shelfSnapshots";
import { photographShelves } from "../shelfPhotos";

vi.mock("@/shared/api/client", () => ({ getShelfViews: vi.fn(), putShelfView: vi.fn() }));
vi.mock("@/features/store-viewer/realistic/shelfSnapshots", () => ({ renderShelfFaces: vi.fn() }));
afterEach(() => vi.resetAllMocks());

const store = { id: "s", name: "S", type: "convenience", grid_size: [10, 10], weekly_schedule: [], racks: [] } as unknown as api.ShelfViewStatus["store"];

it("renders only the faces without a photo and uploads each under its key", async () => {
  vi.mocked(api.getShelfViews).mockResolvedValue({
    currency: "KRW", store,
    faces: [
      { rack_id: "a", rack_name: "A", face: "S", key: "k1", ready: true },
      { rack_id: "b", rack_name: "B", face: "N", key: "k2", ready: false },
      { rack_id: "b", rack_name: "B", face: "S", key: "k3", ready: false },
    ],
  });
  vi.mocked(api.putShelfView).mockResolvedValue({ rack_id: "b", rack_name: "B", face: "N", key: "k2", ready: true });
  vi.mocked(renderShelfFaces).mockImplementation(async (_store, faces, _currency, onShot) => {
    for (const [i, f] of faces.entries()) await onShot(f, { image: `data:image/jpeg;base64,${i}`, width: 768, height: 576, boxes: { [`${f.face}:4:0:0`]: [[1, 2, 30, 40]] } }, i);
  });
  const progress: [number, number][] = [];
  const done = await photographShelves("p", "s", (d, t) => progress.push([d, t]));
  expect(done).toBe(2);
  expect(renderShelfFaces).toHaveBeenCalledWith(store, [{ rackId: "b", face: "N" }, { rackId: "b", face: "S" }], "KRW", expect.any(Function), undefined);
  expect(api.putShelfView).toHaveBeenNthCalledWith(1, "p", "s", "k2", { rack_id: "b", face: "N", image: "data:image/jpeg;base64,0", boxes: { "N:4:0:0": [[1, 2, 30, 40]] } }, undefined);
  expect(api.putShelfView).toHaveBeenNthCalledWith(2, "p", "s", "k3", expect.objectContaining({ face: "S" }), undefined);
  expect(progress).toEqual([[0, 2], [1, 2], [2, 2]]);
});

it("skips rendering when every face already has a photo", async () => {
  vi.mocked(api.getShelfViews).mockResolvedValue({ currency: "USD", store, faces: [{ rack_id: "a", rack_name: "A", face: "S", key: "k1", ready: true }] });
  expect(await photographShelves("p", "s", () => {})).toBe(0);
  expect(renderShelfFaces).not.toHaveBeenCalled();
});
