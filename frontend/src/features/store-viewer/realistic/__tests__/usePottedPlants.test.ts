// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import type { DoorSpec } from "../buildStore";
import { usePottedPlants } from "../usePottedPlants";

const mocks = vi.hoisted(() => ({ load: vi.fn() }));
vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => ({ GLTFLoader: class { loadAsync = mocks.load; } }));
const doors: DoorSpec[] = [{ key: "entry", x: 2, z: 3, yaw: Math.PI / 2, width: 1, tall: true }];
beforeEach(() => { mocks.load.mockReset(); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function plant() {
  const geometry = new THREE.BoxGeometry(0.4, 1.4, 0.4);
  const map = new THREE.Texture();
  const material = new THREE.MeshStandardMaterial({ map, roughnessMap: map });
  const scene = new THREE.Group();
  scene.add(new THREE.Mesh(geometry, material), new THREE.Mesh(geometry, material));
  return { scene, geometry, material, map };
}

it("avoids loading the photographic plant when disabled", () => {
  const hook = renderHook(() => usePottedPlants(false, doors));
  expect(hook.result.current).toBeNull();
  expect(mocks.load).not.toHaveBeenCalled();
  hook.unmount();
});

it("shares model resources between metric planters and releases each resource once", async () => {
  const model = plant();
  const image = { close: vi.fn() };
  class Bitmap { close = image.close; }
  vi.stubGlobal("ImageBitmap", Bitmap);
  model.map.image = new Bitmap();
  const disposed = [model.geometry, model.material, model.map].map((resource) => vi.spyOn(resource, "dispose"));
  mocks.load.mockResolvedValue({ scene: model.scene });
  const hook = renderHook(({ enabled }) => usePottedPlants(enabled, doors), { initialProps: { enabled: true } });
  await act(async () => {});
  const group = hook.result.current!;
  group.updateMatrixWorld(true);
  const planters = group.children[0]!.children;
  expect(planters).toHaveLength(2);
  for (const planter of planters) {
    const bounds = new THREE.Box3().setFromObject(planter);
    expect(bounds.min.y).toBeCloseTo(-0.03, 5);
    expect(bounds.getSize(new THREE.Vector3()).y).toBeCloseTo(1.4 * 0.8, 5);
    expect(bounds.getCenter(new THREE.Vector3()).x).toBeCloseTo(2 - 0.55, 5);
  }
  const mesh = planters[0]!.children[0]!.children[0] as THREE.Mesh;
  expect(mesh.geometry).toBe(model.geometry);
  expect(mesh.material).toBe(model.material);
  hook.rerender({ enabled: false });
  expect(hook.result.current).toBeNull();
  hook.unmount();
  disposed.forEach((dispose) => expect(dispose).toHaveBeenCalledOnce());
  expect(image.close).toHaveBeenCalledOnce();
});

it("discards late loads and never reuses a disposed plant after a quality round trip", async () => {
  const pending: ((value: { scene: THREE.Group }) => void)[] = [];
  mocks.load.mockImplementation(() => new Promise((resolve) => pending.push(resolve)));
  const hook = renderHook(({ enabled }) => usePottedPlants(enabled, doors), { initialProps: { enabled: true } });
  hook.rerender({ enabled: false });
  hook.rerender({ enabled: true });
  const stale = plant(), current = plant();
  const staleDispose = vi.spyOn(stale.map, "dispose"), currentDispose = vi.spyOn(current.map, "dispose");
  await act(async () => { pending[0]!({ scene: stale.scene }); });
  expect(hook.result.current).toBeNull();
  expect(staleDispose).toHaveBeenCalledOnce();
  await act(async () => { pending[1]!({ scene: current.scene }); });
  expect(hook.result.current?.children).toHaveLength(1);
  hook.unmount();
  expect(currentDispose).toHaveBeenCalledOnce();
});

it("keeps the procedural fallback when loading fails", async () => {
  mocks.load.mockRejectedValue(new Error("missing plant"));
  const hook = renderHook(() => usePottedPlants(true, doors));
  await act(async () => {});
  expect(hook.result.current).toBeNull();
  hook.unmount();
});
