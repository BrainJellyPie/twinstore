// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import * as THREE from "three";
import { createShellMaterials, disposeMaterials } from "../materials";
import { INTERIOR_DESIGNS } from "../designThemes";
import type { StoreDesign } from "@/shared/types/domain";

vi.mock("../canvasArt", () => ({
  createAoCanvas: () => document.createElement("canvas"),
  createWoodCanvas: () => document.createElement("canvas"),
}));

it.each(["nordic", "retro"] as const)("keeps %s finishes in both quality modes without mutating adjacent floors", (theme) => {
  const sign = new THREE.Texture();
  for (const quality of ["medium", "high"] as const) {
    const neighbor = createShellMaterials(quality, sign, null, null, null, "classic");
    const materials = createShellMaterials(quality, sign, null, null, null, theme);
    for (const [material, color] of [["wall", "wall"], ["band", "band"], ["bandLine", "accent"], ["metalWhite", "shelf"], ["backPanel", "backing"], ["counterTop", "counter"], ["wood", "wood"], ["ceiling", "ceiling"]] as const) {
      const actual = materials[material] as THREE.MeshStandardMaterial;
      expect(`#${actual.color.getHexString()}`).toBe(INTERIOR_DESIGNS[theme][color]);
      expect(actual).not.toBe(neighbor[material]);
    }
    disposeMaterials(materials);
    expect(`#${(neighbor.wall as THREE.MeshStandardMaterial).color.getHexString()}`).toBe(INTERIOR_DESIGNS.classic.wall);
    disposeMaterials(neighbor);
  }
  sign.dispose();
});

it("applies independent interior finishes without altering shared sign assets", () => {
  const sign = new THREE.Texture();
  const disposed = vi.spyOn(sign, "dispose");
  const classic = createShellMaterials("medium", sign);
  const warm = createShellMaterials("medium", sign, null, null, null, "warm");
  const industrial = createShellMaterials("high", sign, null, null, null, "industrial");
  const coastal = createShellMaterials("medium", sign, null, null, null, "coastal");
  const terracotta = createShellMaterials("high", sign, null, null, null, "terracotta");
  const color = (material: THREE.Material) => (material as THREE.MeshStandardMaterial).color.getHexString();
  const palettes = [classic, warm, industrial, coastal, terracotta];
  expect(new Set(palettes.map((palette) => color(palette.wall))).size).toBe(5);
  expect(new Set(palettes.map((palette) => color(palette.metalWhite))).size).toBe(5);
  const original = color(classic.counterTop);
  disposeMaterials(warm);
  expect(color(classic.counterTop)).toBe(original);
  expect((classic.sign as THREE.MeshStandardMaterial).map).toBe(sign);
  expect(disposed).not.toHaveBeenCalled();
  disposeMaterials(classic);
  disposeMaterials(industrial);
  disposeMaterials(coastal);
  disposeMaterials(terracotta);
  sign.dispose();
});

it("owns surface-map copies without disposing the loader's shared textures", () => {
  const sign = new THREE.Texture();
  const maps = { map: new THREE.Texture(), roughnessMap: new THREE.Texture(), normalMap: new THREE.Texture() };
  const borrowed = Object.values(maps).map((map) => vi.spyOn(map, "dispose"));
  const materials = createShellMaterials("high", sign, null, null, null, "classic", maps, maps);
  const owned = [materials.aluminum, materials.metalGrey, materials.pavement].flatMap((source) => {
    const material = source as THREE.MeshStandardMaterial;
    expect(material.metalness).toBe(material.name === "pavement" ? 0 : 1);
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

it.each(Object.keys(INTERIOR_DESIGNS) as StoreDesign[])("retains %s stone tint and independent map ownership across quality changes", (theme) => {
  const sign = new THREE.Texture();
  const maps = { map: new THREE.Texture(), roughnessMap: new THREE.Texture(), normalMap: new THREE.Texture() };
  const borrowed = Object.values(maps).map(texture => vi.spyOn(texture, "dispose"));
  const high = createShellMaterials("high", sign, null, null, null, theme, null, null, maps);
  const medium = createShellMaterials("medium", sign, null, null, null, theme, null, null, maps);
  const stone = high.counterTop as THREE.MeshPhysicalMaterial;
  const plain = medium.counterTop as THREE.MeshStandardMaterial;
  expect(stone.color.getHexString()).toBe(INTERIOR_DESIGNS[theme].counter.slice(1));
  expect(plain.color.equals(stone.color)).toBe(true);
  expect(stone.metalness).toBe(0);
  expect(stone.roughness).toBe(1);
  expect(stone.clearcoat).toBe(0);
  expect(plain.map).toBeNull();
  const owned = [stone.map!, stone.roughnessMap!, stone.normalMap!].map((texture, i) => {
    expect(texture).not.toBe(Object.values(maps)[i]);
    expect(texture.source).toBe(Object.values(maps)[i]!.source);
    return vi.spyOn(texture, "dispose");
  });
  disposeMaterials(high);
  owned.forEach(dispose => expect(dispose).toHaveBeenCalledOnce());
  borrowed.forEach(dispose => expect(dispose).not.toHaveBeenCalled());
  disposeMaterials(medium);
  Object.values(maps).forEach(texture => texture.dispose());
  sign.dispose();
});
