import { afterEach, describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { HDRLoader } from "three/examples/jsm/loaders/HDRLoader.js";
import { acquirePhotographicEnvironment, acquireRoomEnvironment, releaseRoomEnvironment, retainRoomEnvironment } from "../envCache";

vi.mock("three", async (original) => {
  const actual = await original<typeof import("three")>();
  return {
    ...actual,
    PMREMGenerator: class {
      fromScene() { return new actual.WebGLRenderTarget(16, 16); }
      fromEquirectangular() { return new actual.WebGLRenderTarget(16, 16); }
      dispose() {}
    },
  };
});

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe("store environment cache", () => {
  it("shares one HDR request and releases render targets after the last owner", async () => {
    vi.useFakeTimers();
    const gl = {} as THREE.WebGLRenderer;
    const hdr = new THREE.DataTexture();
    const disposeHdr = vi.spyOn(hdr, "dispose");
    const disposeTarget = vi.spyOn(THREE.WebGLRenderTarget.prototype, "dispose");
    const load = vi.spyOn(HDRLoader.prototype, "loadAsync").mockResolvedValue(hdr);
    const fallback = acquireRoomEnvironment(gl);
    retainRoomEnvironment(gl);
    retainRoomEnvironment(gl);
    const first = acquirePhotographicEnvironment(gl);
    expect(acquirePhotographicEnvironment(gl)).toBe(first);
    const photo = await first;
    expect(photo).not.toBe(fallback);
    expect(load).toHaveBeenCalledOnce();
    expect(disposeHdr).toHaveBeenCalledOnce();
    releaseRoomEnvironment(gl);
    await vi.runAllTimersAsync();
    expect(disposeTarget).not.toHaveBeenCalled();
    releaseRoomEnvironment(gl);
    await vi.runAllTimersAsync();
    expect(disposeTarget).toHaveBeenCalledTimes(2);
  });

  it("keeps the procedural environment when the HDR file is unavailable", async () => {
    vi.useFakeTimers();
    const gl = {} as THREE.WebGLRenderer;
    vi.spyOn(HDRLoader.prototype, "loadAsync").mockRejectedValue(new Error("offline"));
    const fallback = acquireRoomEnvironment(gl);
    retainRoomEnvironment(gl);
    expect(await acquirePhotographicEnvironment(gl)).toBeNull();
    expect(acquireRoomEnvironment(gl)).toBe(fallback);
    releaseRoomEnvironment(gl);
    await vi.runAllTimersAsync();
  });

  it("disposes a late HDR without allocating a new target for a closed viewer", async () => {
    vi.useFakeTimers();
    const gl = {} as THREE.WebGLRenderer;
    const hdr = new THREE.DataTexture();
    const disposeHdr = vi.spyOn(hdr, "dispose");
    const prefilter = vi.spyOn(THREE.PMREMGenerator.prototype, "fromEquirectangular");
    let resolve!: (texture: THREE.DataTexture) => void;
    vi.spyOn(HDRLoader.prototype, "loadAsync").mockReturnValue(new Promise((done) => { resolve = done; }));
    acquireRoomEnvironment(gl);
    retainRoomEnvironment(gl);
    const pending = acquirePhotographicEnvironment(gl);
    releaseRoomEnvironment(gl);
    await vi.runAllTimersAsync();
    resolve(hdr);
    expect(await pending).toBeNull();
    expect(disposeHdr).toHaveBeenCalledOnce();
    expect(prefilter).not.toHaveBeenCalled();
  });
});
