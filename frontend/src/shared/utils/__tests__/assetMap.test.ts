import { describe, expect, it } from "vitest";
import { ALL_REALISTIC_CHARACTER_ASSETS, realisticCharacterAssetFor } from "../assetMap";

describe("photographic shopper selection", () => {
  const ids = ["", "shopper-0", "고객-17", "🛒👤", "Aa".repeat(4096), "2147483648", "-1"];
  it.each(ids)("keeps every ID in the requested appearance pool: %s", (id) => {
    for (const gender of ["Female", "Male", "Unknown", undefined]) {
      const asset = realisticCharacterAssetFor(id, gender);
      expect(ALL_REALISTIC_CHARACTER_ASSETS).toContain(asset);
      expect(realisticCharacterAssetFor(id, gender)).toBe(asset);
      if (gender === "Female") expect(asset).toMatch(/\/female-\d+\.glb$/);
      if (gender === "Male") expect(asset).toMatch(/\/male-\d+\.glb$/);
    }
  });

  it("makes every bundled appearance reachable for sequential shoppers", () => {
    const selected = new Set(Array.from({ length: 1000 }, (_, i) => realisticCharacterAssetFor(`shopper-${i}`)));
    expect([...selected].sort()).toEqual([...ALL_REALISTIC_CHARACTER_ASSETS].sort());
    expect(new Set(ALL_REALISTIC_CHARACTER_ASSETS).size).toBe(ALL_REALISTIC_CHARACTER_ASSETS.length);
    expect(realisticCharacterAssetFor("female-casual-0", "Female")).toBe("/assets/people/female-17.glb");
    expect(realisticCharacterAssetFor("male-casual-4", "Male")).toBe("/assets/people/male-10.glb");
  });
});
