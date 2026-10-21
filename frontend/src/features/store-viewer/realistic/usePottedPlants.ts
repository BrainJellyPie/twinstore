import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { DoorSpec } from "./buildStore";
import { M } from "./constants";

function disposePlant(scene: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const images = new Set<ImageBitmap>();
  scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
  });
  for (const material of materials) for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
  for (const texture of textures) {
    const image: unknown = texture.image;
    if (typeof ImageBitmap !== "undefined" && image instanceof ImageBitmap) images.add(image);
    texture.dispose();
  }
  images.forEach((image) => image.close());
  materials.forEach((material) => material.dispose());
  geometries.forEach((geometry) => geometry.dispose());
}

export function usePottedPlants(enabled: boolean, doors: DoorSpec[]) {
  const request = useMemo(() => ({ enabled }), [enabled]);
  const [loaded, setLoaded] = useState<{ request: typeof request; scene: THREE.Group } | null>(null);

  useEffect(() => {
    if (!request.enabled) return;
    let alive = true;
    let scene: THREE.Group | null = null;
    void new GLTFLoader().loadAsync("/assets/props/potted-plant-01.glb").then((gltf) => {
      if (!alive) { disposePlant(gltf.scene); return; }
      scene = gltf.scene;
      scene.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return;
        object.castShadow = object.receiveShadow = true;
        object.raycast = () => undefined;
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
          if (material.alphaTest > 0) material.alphaToCoverage = true;
        }
      });
      setLoaded({ request, scene });
    }).catch(() => { /* The procedural planters stay visible if the asset cannot load. */ });
    return () => {
      alive = false;
      if (scene) disposePlant(scene);
    };
  }, [request]);

  return useMemo(() => {
    if (!loaded || loaded.request !== request) return null;
    const source = loaded.scene;
    const bounds = new THREE.Box3().setFromObject(source);
    const offset = bounds.getCenter(new THREE.Vector3()).multiplyScalar(-1);
    offset.y = -bounds.min.y;
    const group = new THREE.Group();
    group.name = "scanned-planters";
    for (const door of doors) {
      const doorway = new THREE.Group();
      doorway.position.set(door.x, 0, door.z);
      doorway.rotation.y = door.yaw;
      for (const sign of [-1, 1]) {
        const planter = new THREE.Group();
        // Match the fallback pots, with the base resting on the pavement at -0.03.
        planter.position.set(sign * (door.width / 2 + 0.45), -0.03, -0.55);
        planter.rotation.y = sign * 0.35;
        planter.scale.setScalar(M);
        const clone = source.clone(true);
        clone.position.copy(offset);
        planter.add(clone);
        doorway.add(planter);
      }
      group.add(doorway);
    }
    return group;
  }, [loaded, request, doors]);
}
