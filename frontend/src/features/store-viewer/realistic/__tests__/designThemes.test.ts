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
