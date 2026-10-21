import { hash01, type PackageKind } from "./productCatalog";

/** Stable visual variation; never changes the assortment or stocking layout. */
export function produceVariation(kind: PackageKind, key: string) {
  if (kind !== "apple" && kind !== "applePair" && kind !== "banana" && kind !== "avocado") return null;
  return {
    // Leave clearance for a single apple's slightly asymmetric scanned outline.
    scale: kind === "apple" ? 0.90 + 0.04 * hash01(key, 41) : 0.94 + 0.06 * hash01(key, 41),
    // Other scanned fruit retain their asymmetric footprint when turned halfway.
    yaw: kind === "apple" ? hash01(key, 42) * Math.PI * 2 : (hash01(key, 42) < 0.5 ? 0 : Math.PI),
    brightness: 0.88 + 0.12 * hash01(key, 43),
  };
}
