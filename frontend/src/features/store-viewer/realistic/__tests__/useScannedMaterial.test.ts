// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { useScannedMaterial } from "../useScannedMaterial";
import type { GraphicsQuality } from "../constants";

function pendingLoads() {
  const pending: { url: string; resolve: (texture: THREE.Texture<HTMLImageElement>) => void; reject: (error: Error) => void }[] = [];
  vi.spyOn(THREE.TextureLoader.prototype, "loadAsync").mockImplementation((url) =>
    new Promise((resolve, reject) => pending.push({ url, resolve, reject })),
  );
  return pending;
}

afterEach(() => vi.restoreAllMocks());

describe("scanned material lifecycle", () => {
  it("publishes a complete set with linear data maps and real-world repeats", async () => {
    const loads = pendingLoads();
    const hook = renderHook(() => useScannedMaterial("floor_tiles_08", 4, 5, "high"));
    const textures = loads.map(() => new THREE.Texture<HTMLImageElement>());
    await act(async () => { loads[0]!.resolve(textures[0]!); });
    expect(hook.result.current).toBeNull();
    await act(async () => { loads.slice(1).forEach((load, i) => load.resolve(textures[i + 1]!)); });
    expect(hook.result.current?.map.colorSpace).toBe(THREE.SRGBColorSpace);
    expect(hook.result.current?.normalMap?.colorSpace).toBe(THREE.NoColorSpace);
    expect(hook.result.current?.roughnessMap.colorSpace).toBe(THREE.NoColorSpace);
    expect(hook.result.current?.map.repeat.toArray()).toEqual([4, 5]);
    hook.unmount();
  });

  it("keeps the fallback and releases successful and late loads after a failed map", async () => {
    const loads = pendingLoads();
    const hook = renderHook(() => useScannedMaterial("floor_tiles_08", 1, 1, "high"));
    const early = new THREE.Texture<HTMLImageElement>(), late = new THREE.Texture<HTMLImageElement>();
    const earlyDispose = vi.spyOn(early, "dispose"), lateDispose = vi.spyOn(late, "dispose");
    await act(async () => { loads[0]!.resolve(early); });
    await act(async () => { loads[1]!.reject(new Error("missing asset")); });
    await act(async () => { loads[2]!.resolve(late); });
    expect(hook.result.current).toBeNull();
    expect(earlyDispose).toHaveBeenCalledOnce();
    expect(lateDispose).toHaveBeenCalledOnce();
    hook.unmount();
    expect(earlyDispose).toHaveBeenCalledOnce();
  });

  it("ignores old quality requests and releases resources arriving after unmount", async () => {
    const loads = pendingLoads();
    const hook = renderHook(({ quality }: { quality: GraphicsQuality }) =>
      useScannedMaterial("wood_table_001", 1, 1, quality), { initialProps: { quality: "high" } });
    hook.rerender({ quality: "medium" });
    expect(loads).toHaveLength(5); // Medium skips the normal map.
    const stale = loads.slice(0, 3).map(() => new THREE.Texture<HTMLImageElement>());
    const dispose = stale.map((texture) => vi.spyOn(texture, "dispose"));
    await act(async () => { loads.slice(0, 3).forEach((load, i) => load.resolve(stale[i]!)); });
    expect(hook.result.current).toBeNull();
    dispose.forEach((spy) => expect(spy).toHaveBeenCalledOnce());
    hook.unmount();
    const late = new THREE.Texture<HTMLImageElement>();
    const lateDispose = vi.spyOn(late, "dispose");
    await act(async () => { loads[3]!.resolve(late); loads[4]!.reject(new Error("cancelled")); });
    expect(lateDispose).toHaveBeenCalledOnce();
  });
});
