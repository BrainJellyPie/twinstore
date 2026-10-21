// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, renderHook } from "@testing-library/react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";

import { useGlbModel } from "../useGlbModel";

vi.mock("@react-three/drei", () => ({ useGLTF: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function model(material: THREE.Material | THREE.Material[]) {
  const scene = new THREE.Group();
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(), material));
  vi.mocked(useGLTF).mockReturnValue({ scene, animations: [] } as unknown as ReturnType<typeof useGLTF>);
}

it("isolates a texture override and restores the original texture when it is removed", () => {
  const original = new THREE.Texture();
  const override = new THREE.Texture();
  const cached = new THREE.MeshStandardMaterial({ map: original });
  const disposeCached = vi.spyOn(cached, "dispose");
  const disposeTexture = vi.spyOn(override, "dispose");
  model(cached);
  const { result, rerender, unmount } = renderHook(({ map }) => useGlbModel("model.glb", { overrideMap: map }), {
    initialProps: { map: override as THREE.Texture | null },
  });
  const material = (result.current.clone.children[0] as THREE.Mesh).material as THREE.MeshStandardMaterial;
  expect(material.map).toBe(override);
  expect(cached.map).toBe(original);
  expect(material).not.toBe(cached);
  const disposeOverride = vi.spyOn(material, "dispose");

  rerender({ map: null });

  expect(((result.current.clone.children[0] as THREE.Mesh).material as THREE.MeshStandardMaterial).map).toBe(original);
  expect(disposeOverride).toHaveBeenCalledTimes(1);
  unmount();
  expect(disposeCached).not.toHaveBeenCalled();
  expect(disposeTexture).not.toHaveBeenCalled();
});

it("applies overrides to each textured material of a mesh without changing cached materials", () => {
  const original = new THREE.Texture();
  const override = new THREE.Texture();
  const materials = [new THREE.MeshStandardMaterial({ map: original }), new THREE.MeshBasicMaterial({ map: original })];
  model(materials);
  const { result } = renderHook(() => useGlbModel("multi.glb", { overrideMap: override }));
  const copies = (result.current.clone.children[0] as THREE.Mesh).material as typeof materials;

  expect(copies.map((m) => m.map)).toEqual([override, override]);
  expect(materials.map((m) => m.map)).toEqual([original, original]);
});
