import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { loadScannedProducts } from "../scannedProducts";
import type { ProductLod } from "../productMeshes";

const mocks = vi.hoisted(() => ({ load: vi.fn() }));
vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => ({ GLTFLoader: class { loadAsync = mocks.load; } }));
beforeEach(() => { mocks.load.mockReset(); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function fallback(): ProductLod {
  const coarse = new THREE.BoxGeometry(), fine = new THREE.SphereGeometry();
  return { coarse, fine, mesh: new THREE.InstancedMesh(fine, new THREE.MeshStandardMaterial(), 12) };
}

function scan() {
  const coarse = new THREE.BoxGeometry(), fine = new THREE.SphereGeometry();
  const map = new THREE.Texture();
  const material = new THREE.MeshStandardMaterial({ map, normalMap: map, roughnessMap: map });
  const scene = new THREE.Group();
  scene.add(Object.assign(new THREE.Mesh(coarse, material), { name: "bananas-coarse" }));
  scene.add(Object.assign(new THREE.Mesh(fine, material), { name: "bananas-fine" }));
  return { coarse, fine, map, material, scene };
}

it("keeps the selected LOD and restores borrowed fallback resources on cleanup", async () => {
  const target = fallback(), original = { ...target, material: target.mesh.material };
  const model = scan();
  const bitmapClose = vi.fn();
  class Bitmap { close = bitmapClose; }
  vi.stubGlobal("ImageBitmap", Bitmap);
  model.map.image = new Bitmap();
  const disposed = [model.coarse, model.fine, model.map, model.material].map((r) => vi.spyOn(r, "dispose"));
  const fallbackDispose = vi.spyOn(original.fine, "dispose");
  const ready = vi.fn();
  mocks.load.mockResolvedValue({ scene: model.scene });
  const stop = loadScannedProducts("/assets/produce/bananas.glb", [{ lod: target, name: "bananas" }], false, ready);
  await Promise.resolve();
  expect(target.mesh.geometry).not.toBe(model.fine);
  expect(Array.from(target.mesh.geometry.attributes.position!.array, (v) => v || 0)).toEqual(Array.from(model.fine.attributes.position!.array, (v) => v || 0));
  const disposeBaked = [target.coarse, target.fine].map((geometry) => vi.spyOn(geometry, "dispose"));
  expect(target.mesh.material).toBe(model.material);
  expect(target.mesh.count).toBe(12);
  expect(ready).toHaveBeenCalledOnce();
  target.mesh.geometry = target.coarse;
  stop(); stop();
  expect(target.mesh.geometry).toBe(original.coarse);
  expect(target.mesh.material).toBe(original.material);
  expect(target.mesh.userData.scannedProducts).toBeUndefined();
  [...disposed, ...disposeBaked].forEach((dispose) => expect(dispose).toHaveBeenCalledOnce());
  expect(bitmapClose).toHaveBeenCalledOnce();
  expect(fallbackDispose).not.toHaveBeenCalled();
});

it("uses a lighter medium material while retaining ownership of unused source maps", async () => {
  const target = fallback(), model = scan();
  model.material.metalness = 1;
  model.material.metalnessMap = model.map;
  mocks.load.mockResolvedValue({ scene: model.scene });
  const disposeMap = vi.spyOn(model.map, "dispose");
  const stop = loadScannedProducts("/assets/produce/bananas.glb", [{ lod: target, name: "bananas", roughness: 0.85 }], true);
  await Promise.resolve();
  const medium = target.mesh.material as THREE.MeshStandardMaterial;
  expect(medium).not.toBe(model.material);
  expect(medium.map).toBe(model.map);
  expect(medium.normalMap).toBeNull();
  expect(medium.roughnessMap).toBeNull();
  expect(medium.roughness).toBe(0.85);
  expect(medium.metalness).toBe(0);
  expect(medium.metalnessMap).toBeNull();
  expect(model.material.metalness).toBe(1);
  expect(model.material.metalnessMap).toBe(model.map);
  expect(model.material.normalMap).toBe(model.map);
  const disposeMedium = vi.spyOn(medium, "dispose");
  stop();
  expect(disposeMedium).toHaveBeenCalledOnce();
  expect(disposeMap).toHaveBeenCalledOnce();
});

it("discards late requests without replacing a newer scan", async () => {
  const pending: ((result: { scene: THREE.Group }) => void)[] = [];
  mocks.load.mockImplementation(() => new Promise((resolve) => pending.push(resolve)));
  const target = fallback(), stale = scan(), current = scan();
  const staleDispose = vi.spyOn(stale.map, "dispose");
  const stopOld = loadScannedProducts("/assets/produce/bananas.glb", [{ lod: target, name: "bananas" }], false);
  stopOld();
  const stopCurrent = loadScannedProducts("/assets/produce/bananas.glb", [{ lod: target, name: "bananas" }], false);
  pending[1]!({ scene: current.scene }); await Promise.resolve();
  pending[0]!({ scene: stale.scene }); await Promise.resolve();
  expect(target.mesh.material).toBe(current.material);
  expect(staleDispose).toHaveBeenCalledOnce();
  stopOld();
  expect(target.mesh.material).toBe(current.material);
  stopCurrent();
});

it("keeps the curved fallback on a failed asset load", async () => {
  const target = fallback(), material = target.mesh.material;
  mocks.load.mockRejectedValue(new Error("missing asset"));
  const stop = loadScannedProducts("/assets/produce/bananas.glb", [{ lod: target, name: "bananas" }], false);
  await Promise.resolve(); await Promise.resolve();
  expect(target.mesh.material).toBe(material);
  expect(target.mesh.userData.scannedProducts).toBeUndefined();
  stop();
});

it("bakes shared buffers independently and releases a shared medium material once", async () => {
  const first = fallback(), second = fallback(), model = scan();
  const originals = [first.mesh.material, second.mesh.material];
  const sourcePositions = Array.from(model.fine.attributes.position!.array);
  for (const detail of ["coarse", "fine"]) {
    const source = model.scene.getObjectByName(`bananas-${detail}`) as THREE.Mesh;
    const other = source.clone();
    other.name = `pair-${detail}`;
    source.position.x = 2;
    other.position.x = -3;
    model.scene.add(other);
  }
  const disposeSource = vi.spyOn(model.fine, "dispose"), disposeMap = vi.spyOn(model.map, "dispose");
  mocks.load.mockResolvedValue({ scene: model.scene });
  const stop = loadScannedProducts("/assets/produce/test.glb", [{ lod: first, name: "bananas" }, { lod: second, name: "pair" }], true);
  await Promise.resolve();
  expect(mocks.load).toHaveBeenCalledOnce();
  expect(first.mesh.material).toBe(second.mesh.material);
  expect(first.fine.attributes.position!.getX(0)).toBeCloseTo(sourcePositions[0]! + 2);
  expect(second.fine.attributes.position!.getX(0)).toBeCloseTo(sourcePositions[0]! - 3);
  expect(Array.from(model.fine.attributes.position!.array)).toEqual(sourcePositions);
  const disposeMedium = vi.spyOn(first.mesh.material as THREE.Material, "dispose");
  stop();
  expect([first.mesh.material, second.mesh.material]).toEqual(originals);
  [disposeSource, disposeMap, disposeMedium].forEach((dispose) => expect(dispose).toHaveBeenCalledOnce());
});
