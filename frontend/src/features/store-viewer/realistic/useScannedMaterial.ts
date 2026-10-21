import { useEffect, useState } from "react";
import * as THREE from "three";
import type { GraphicsQuality } from "./constants";

export interface ScannedMaterialMaps {
  map: THREE.Texture;
  roughnessMap: THREE.Texture;
  normalMap: THREE.Texture | null;
}

type Surface = "floor_tiles_08" | "wood_table_001";

// Bundled CC0 scans: no CDN dependency at runtime. Keep the procedural surface
// visible until the entire set is ready, including when a download fails.
export function useScannedMaterial(surface: Surface, repeatX: number, repeatY: number, quality: GraphicsQuality) {
  const key = `${surface}:${repeatX}:${repeatY}:${quality}`;
  const [loaded, setLoaded] = useState<{ key: string; maps: ScannedMaterialMaps } | null>(null);

  useEffect(() => {
    let alive = true;
    const textures: THREE.Texture[] = [];
    const loader = new THREE.TextureLoader();
    const load = async (suffix: string, color: boolean) => {
      const texture = await loader.loadAsync(`/assets/materials/${surface}_${suffix}_1k.jpg`);
      if (!alive) {
        texture.dispose();
        return texture;
      }
      texture.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
      texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.repeat.set(repeatX, repeatY);
      texture.anisotropy = quality === "high" ? 8 : 2;
      textures.push(texture);
      return texture;
    };

    void Promise.all([
      load("diff", true),
      load("rough", false),
      quality === "high" ? load("nor_gl", false) : Promise.resolve(null),
    ]).then(([map, roughnessMap, normalMap]) => {
      if (alive) setLoaded({ key, maps: { map, roughnessMap, normalMap } });
    }).catch(() => {
      alive = false;
      textures.forEach((texture) => texture.dispose());
      textures.length = 0;
    });

    return () => {
      alive = false;
      textures.forEach((texture) => texture.dispose());
    };
  }, [key, surface, repeatX, repeatY, quality]);

  return loaded?.key === key ? loaded.maps : null;
}
