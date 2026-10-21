import { expect, it } from "vitest";
import { PACKAGE_KINDS } from "../productGeometries";
import { produceVariation } from "../produceVariation";

it("keeps fruit variation deterministic, subtle and restricted to fresh produce", () => {
  for (const kind of PACKAGE_KINDS) {
    const values = Array.from({ length: 64 }, (_, i) => produceVariation(kind, `${kind}|${i}|0|0`));
    if (!["apple", "applePair", "banana"].includes(kind)) {
      expect(values.every((value) => value === null)).toBe(true);
      continue;
    }
    expect(new Set(values.map((value) => value!.scale)).size).toBeGreaterThan(60);
    values.forEach((value, i) => {
      expect(produceVariation(kind, `${kind}|${i}|0|0`)).toEqual(value);
      expect(value!.scale).toBeGreaterThanOrEqual(0.90);
      expect(value!.scale).toBeLessThanOrEqual(kind === "apple" ? 0.94 : 1);
      expect(value!.brightness).toBeGreaterThanOrEqual(0.88);
      expect(value!.brightness).toBeLessThanOrEqual(1);
      if (kind !== "apple") expect([0, Math.PI]).toContain(value!.yaw);
    });
  }
});
