// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { StrictMode } from "react";
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
  const cancellationCases = [0, 1, 2].flatMap((failed) =>
    [0, 1, 2].filter((early) => early !== failed).flatMap((early) =>
      (["unmount", "disable", "resize"] as const).map((change) => ({ failed, early, change }))),
  );
  it.each(cancellationCases)("releases maps exactly once after $change, then failure $failed (early $early)", async ({ failed, early, change }) => {
    const loads = pendingLoads();
    const hook = renderHook(({ enabled, width }) =>
      useScannedMaterial(enabled ? "office_ceiling_001" : null, width / 3, 5 / 3, "high", 1 / 12),
    { initialProps: { enabled: true, width: 4 } });
    const textures = loads.map(() => new THREE.Texture<HTMLImageElement>());
    const disposed = textures.map((texture) => vi.spyOn(texture, "dispose"));
    await act(async () => { loads[early]!.resolve(textures[early]!); });
    if (change === "unmount") hook.unmount();
    else hook.rerender({ enabled: change !== "disable", width: 7 });
    const replacement = loads.slice(3).map(() => new THREE.Texture<HTMLImageElement>());
    await act(async () => { loads.slice(3).forEach((load, i) => load.resolve(replacement[i]!)); });
    await act(async () => { loads[failed]!.reject(new Error("late network failure")); });
    const late = 3 - failed - early;
    await act(async () => { loads[late]!.resolve(textures[late]!); });
    if (change === "resize") {
      expect(hook.result.current?.map).toBe(replacement[0]);
      expect(hook.result.current?.map.repeat.toArray()).toEqual([7 / 3, 5 / 3]);
    } else expect(hook.result.current).toBeNull();
    if (change !== "unmount") hook.unmount();
    expect(disposed[early]).toHaveBeenCalledOnce();
    expect(disposed[late]).toHaveBeenCalledOnce();
    expect(disposed[failed]).not.toHaveBeenCalled();
  });

  it.each([[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]])(
    "publishes ceiling maps atomically with completion order %s, %s, %s", async (a, b, c) => {
      const loads = pendingLoads();
      const hook = renderHook(() => useScannedMaterial("office_ceiling_001", 0.5, 8, "high", 1 / 12));
      const textures = loads.map(() => new THREE.Texture<HTMLImageElement>());
      for (const index of [a, b]) {
        await act(async () => { loads[index]!.resolve(textures[index]!); });
        expect(hook.result.current).toBeNull();
      }
      await act(async () => { loads[c]!.resolve(textures[c]!); });
      expect(hook.result.current).toEqual({ map: textures[0], roughnessMap: textures[1], normalMap: textures[2] });
      for (const texture of textures) {
        expect(texture.repeat.toArray()).toEqual([0.5, 8]);
        expect(texture.offset.toArray()).toEqual([1 / 12, 1 / 12]);
      }
      hook.unmount();
    },
  );

  it("keeps replayed StrictMode loads independent from the discarded request", async () => {
    const loads = pendingLoads();
    const hook = renderHook(() => useScannedMaterial("office_ceiling_001", 1, 1, "high"), { wrapper: StrictMode });
    expect(loads).toHaveLength(6);
    const textures = loads.map(() => new THREE.Texture<HTMLImageElement>());
    const disposed = textures.map((texture) => vi.spyOn(texture, "dispose"));
    await act(async () => { loads.slice(3).forEach((load, i) => load.resolve(textures[i + 3]!)); });
    await act(async () => { loads.slice(0, 3).forEach((load, i) => load.resolve(textures[i]!)); });
    expect(hook.result.current?.map).toBe(textures[3]);
    disposed.slice(0, 3).forEach((spy) => expect(spy).toHaveBeenCalledOnce());
    disposed.slice(3).forEach((spy) => expect(spy).not.toHaveBeenCalled());
    hook.unmount();
    disposed.forEach((spy) => expect(spy).toHaveBeenCalledOnce());
  });

  it("does not fetch optional surfaces when their quality tier is disabled", () => {
    const loads = pendingLoads();
    const hook = renderHook(() => useScannedMaterial(null, 1, 1, "medium"));
    expect(loads).toHaveLength(0);
    expect(hook.result.current).toBeNull();
    hook.unmount();
  });

  it("does not reuse disposed maps when switching back to an earlier quality", async () => {
    const loads = pendingLoads();
    const hook = renderHook(({ quality }: { quality: GraphicsQuality }) =>
      useScannedMaterial("floor_tiles_08", 1, 1, quality), { initialProps: { quality: "high" } });
    const first = loads.map(() => new THREE.Texture<HTMLImageElement>());
    const disposed = first.map((texture) => vi.spyOn(texture, "dispose"));
    await act(async () => { loads.forEach((load, i) => load.resolve(first[i]!)); });
    expect(hook.result.current?.map).toBe(first[0]);

    hook.rerender({ quality: "medium" });
    hook.rerender({ quality: "high" });
    disposed.forEach((spy) => expect(spy).toHaveBeenCalledOnce());
    expect(hook.result.current).toBeNull();

    const replacement = loads.slice(5).map(() => new THREE.Texture<HTMLImageElement>());
    await act(async () => { loads.slice(5).forEach((load, i) => load.resolve(replacement[i]!)); });
    expect(hook.result.current?.map).toBe(replacement[0]);
    hook.unmount();
  });

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

  it("aligns all ceiling maps at the same phase and releases the previous request when it changes", async () => {
    const loads = pendingLoads();
    const hook = renderHook(({ offset }) => useScannedMaterial("office_ceiling_001", 4 / 3, 5 / 3, "high", offset),
      { initialProps: { offset: 1 / 12 } });
    const textures = loads.map(() => new THREE.Texture<HTMLImageElement>());
    const disposed = textures.map((texture) => vi.spyOn(texture, "dispose"));
    await act(async () => { loads.forEach((load, i) => load.resolve(textures[i]!)); });
    for (const texture of textures) {
      expect(texture.repeat.toArray()).toEqual([4 / 3, 5 / 3]);
      expect(texture.offset.toArray()).toEqual([1 / 12, 1 / 12]);
      // A light centred at world (0.5, 0.5) must sit at a panel centre.
      expect(((0.5 / 4) * texture.repeat.x + texture.offset.x) * 6 % 1).toBeCloseTo(0.5);
      expect(((0.5 / 5) * texture.repeat.y + texture.offset.y) * 6 % 1).toBeCloseTo(0.5);
    }
    hook.rerender({ offset: 0 });
    expect(hook.result.current).toBeNull();
    disposed.forEach((spy) => expect(spy).toHaveBeenCalledOnce());
    expect(loads).toHaveLength(6);
    hook.unmount();
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
