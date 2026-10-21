// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import * as THREE from "three";
import { createShellMaterials, disposeMaterials } from "../materials";
import { INTERIOR_DESIGNS } from "../designThemes";
import { buildPhotoScene } from "../photoScene";
import type { StoreDesign } from "@/shared/types/domain";

vi.mock("../canvasArt", () => ({
  createAoCanvas: () => document.createElement("canvas"),
  createWoodCanvas: () => document.createElement("canvas"),
}));

const cases = (["medium", "high"] as const).flatMap(quality =>
  (Object.keys(INTERIOR_DESIGNS) as StoreDesign[]).map(theme => ({ quality, theme })),
);

it.each(cases)("owns a single display-map copy in $quality / $theme", ({ quality, theme }) => {
  const sign = new THREE.Texture();
  const source = new THREE.CanvasTexture(document.createElement("canvas"));
  source.colorSpace = THREE.SRGBColorSpace;
  const borrowed = vi.spyOn(source, "dispose");
  const mats = createShellMaterials(quality, sign, null, null, null, theme, null, null, null, null, source);
  const screen = mats.screen as THREE.MeshStandardMaterial;
  expect(screen.map).not.toBe(source);
  expect(screen.map!.source).toBe(source.source);
  expect(screen.map!.colorSpace).toBe(THREE.SRGBColorSpace);
  expect(screen.emissiveMap).toBe(screen.map);
  expect(screen.metalness).toBe(0);
  const owned = vi.spyOn(screen.map!, "dispose");
  disposeMaterials(mats);
  expect(owned).toHaveBeenCalledOnce();
  expect(borrowed).not.toHaveBeenCalled();
  source.dispose(); sign.dispose();
});

it("preserves mapped displays and their UVs through repeated Photo snapshots", () => {
  const sign = new THREE.Texture(), source = new THREE.Texture();
  const mats = createShellMaterials("high", sign, null, null, null, "classic", null, null, null, null, source);
  const screen = mats.screen as THREE.MeshStandardMaterial;
  const mapDisposed = vi.spyOn(screen.map!, "dispose");
  const materialDisposed = vi.spyOn(screen, "dispose");
  const geometry = new THREE.PlaneGeometry(0.27, 0.18);
  const uv = geometry.getAttribute("uv");
  for (let i = 0; i < uv.count; i++) uv.setXY(i, 0.01 + uv.getX(i) * 0.48, 0.51 + uv.getY(i) * 0.48);
  const original = Array.from(uv.array);
  const live = new THREE.Scene();
  live.add(new THREE.Mesh(geometry, screen));
  for (let i = 0; i < 3; i++) {
    const photo = buildPhotoScene(live, { width: 4, depth: 5, background: null });
    const mesh = photo.scene.children.find(o => o instanceof THREE.Mesh) as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
    expect(mesh.material).not.toBe(screen);
    expect(mesh.material.map).toBe(screen.map);
    expect(mesh.material.emissiveMap).toBe(screen.map);
    expect(mesh.material.emissiveIntensity).toBe(screen.emissiveIntensity);
    const copiedUv = mesh.geometry.getAttribute("uv");
    for (let k = 0; k < geometry.index!.count; k++) {
      const index = geometry.index!.getX(k);
      expect(copiedUv.getX(k)).toBe(uv.getX(index));
      expect(copiedUv.getY(k)).toBe(uv.getY(index));
    }
    photo.dispose();
    expect(Array.from(uv.array)).toEqual(original);
    expect(mapDisposed).not.toHaveBeenCalled();
    expect(materialDisposed).not.toHaveBeenCalled();
  }
  disposeMaterials(mats);
  expect(mapDisposed).toHaveBeenCalledOnce();
  geometry.dispose(); source.dispose(); sign.dispose();
});
