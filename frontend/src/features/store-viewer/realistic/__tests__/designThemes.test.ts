// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import * as THREE from "three";
import { createShellMaterials, disposeMaterials } from "../materials";

vi.mock("../canvasArt", () => ({
  createAoCanvas: () => document.createElement("canvas"),
  createWoodCanvas: () => document.createElement("canvas"),
}));

it("applies independent interior finishes without altering shared sign assets", () => {
  const sign = new THREE.Texture();
  const disposed = vi.spyOn(sign, "dispose");
  const classic = createShellMaterials("medium", sign);
  const warm = createShellMaterials("medium", sign, null, null, null, "warm");
  const industrial = createShellMaterials("high", sign, null, null, null, "industrial");
  const color = (material: THREE.Material) => (material as THREE.MeshStandardMaterial).color.getHexString();
  expect(new Set([color(classic.wall), color(warm.wall), color(industrial.wall)]).size).toBe(3);
  expect(new Set([color(classic.metalWhite), color(warm.metalWhite), color(industrial.metalWhite)]).size).toBe(3);
  const original = color(classic.counterTop);
  disposeMaterials(warm);
  expect(color(classic.counterTop)).toBe(original);
  expect((classic.sign as THREE.MeshStandardMaterial).map).toBe(sign);
  expect(disposed).not.toHaveBeenCalled();
  disposeMaterials(classic);
  disposeMaterials(industrial);
  sign.dispose();
});

it("owns metal-map copies without disposing the loader's shared textures", () => {
  const sign = new THREE.Texture();
  const maps = { map: new THREE.Texture(), roughnessMap: new THREE.Texture(), normalMap: new THREE.Texture() };
  const borrowed = Object.values(maps).map((map) => vi.spyOn(map, "dispose"));
  const materials = createShellMaterials("high", sign, null, null, null, "classic", maps);
  const owned = [materials.aluminum, materials.metalGrey].flatMap((source) => {
    const material = source as THREE.MeshStandardMaterial;
    expect(material.metalness).toBe(1);
    expect(material.map).not.toBe(maps.map);
    expect(material.map!.source).toBe(maps.map.source);
    return [material.map!, material.roughnessMap!, material.normalMap!].map((texture) => vi.spyOn(texture, "dispose"));
  });
  expect((materials.metalWhite as THREE.MeshStandardMaterial).map).toBeNull();
  disposeMaterials(materials);
  owned.forEach((dispose) => expect(dispose).toHaveBeenCalledOnce());
  borrowed.forEach((dispose) => expect(dispose).not.toHaveBeenCalled());
  Object.values(maps).forEach((map) => map.dispose());
  sign.dispose();
});
