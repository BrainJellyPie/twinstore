import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import type { GraphicsQuality } from "./constants";

export interface ScannedMaterialMaps {
  map: THREE.Texture;
  roughnessMap: THREE.Texture;
  normalMap: THREE.Texture | null;
}

type Surface = "floor_tiles_08" | "wood_table_001" | "plaster_001" | "metal_032" | "pavement_02" | "office_ceiling_001" | "marble_012";

// Bundled CC0 PBR maps: no CDN dependency at runtime. Keep the procedural surface
// visible until the entire set is ready, including when a download fails.
export function useScannedMaterial(surface: Surface | null, repeatX: number, repeatY: number, quality: GraphicsQuality, offset = 0) {
  const request = useMemo(() => ({ surface, repeatX, repeatY, quality, offset }), [surface, repeatX, repeatY, quality, offset]);
  const [loaded, setLoaded] = useState<{ request: typeof request; maps: ScannedMaterialMaps } | null>(null);

  useEffect(() => {
    const { surface, repeatX, repeatY, quality, offset } = request;
    if (!surface) return;
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
      texture.offset.set(offset, offset);
      texture.anisotropy = quality === "high" ? 8 : 2;
      textures.push(texture);
      return texture;
    };

    void Promise.all([
      load("diff", true),
      load("rough", false),
      quality === "high" ? load("nor_gl", false) : Promise.resolve(null),
    ]).then(([map, roughnessMap, normalMap]) => {
      if (alive) setLoaded({ request, maps: { map, roughnessMap, normalMap } });
    }).catch(() => {
      alive = false;
      textures.forEach((texture) => texture.dispose());
      textures.length = 0;
    });

    return () => {
      alive = false;
      textures.forEach((texture) => texture.dispose());
      textures.length = 0;
    };
  }, [request]);

  return loaded?.request === request ? loaded.maps : null;
}
