import { useMemo } from "react";
import * as THREE from "three";

import { RAMPS, ramp, type HeatmapPalette } from "../utils/heatmapPalette";

interface HeatmapOverlayProps {
  data: number[][]; // values in [0, 1], [row][col]
  palette: HeatmapPalette;
  width: number;
  depth: number;
}

export function HeatmapOverlay({ data, palette, width, depth }: HeatmapOverlayProps) {
  const texture = useMemo(() => {
    const stops = RAMPS[palette];
    const pixels = new Uint8Array(width * depth * 4);
    for (let y = 0; y < depth; y++) {
      for (let x = 0; x < width; x++) {
        const v = Math.max(0, Math.min(1, data[y]?.[x] ?? 0));
        const py = depth - 1 - y;
        const i = (py * width + x) * 4;
        const [r, g, b] = ramp(stops, v);
        pixels[i] = r;
        pixels[i + 1] = g;
        pixels[i + 2] = b;
        pixels[i + 3] = v > 0 ? Math.round(70 + 150 * v) : 0;
      }
    }
    const tex = new THREE.DataTexture(pixels, width, depth, THREE.RGBAFormat);
    tex.magFilter = THREE.LinearFilter;
    tex.minFilter = THREE.LinearFilter;
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.needsUpdate = true;
    return tex;
  }, [data, width, depth, palette]);

  return (
    <mesh position={[width / 2, 0.05, depth / 2]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[width, depth]} />
      <meshBasicMaterial map={texture} transparent depthWrite={false} />
    </mesh>
  );
}
