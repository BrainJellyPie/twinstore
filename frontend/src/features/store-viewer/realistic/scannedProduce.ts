import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { disposeOwnedGltf } from "./gltfResources";
import type { ProductLod } from "./productMeshes";

export interface ScannedProduceTarget { lod: ProductLod; name: string }

export function loadScannedProduce(url: string, targets: ScannedProduceTarget[], cheap: boolean, onReady?: () => void): () => void {
  const fallbacks = targets.map(({ lod }) => ({ lod, coarse: lod.coarse, fine: lod.fine, material: lod.mesh.material }));
  let alive = true;
  let owned: THREE.Group | null = null;
  const geometries: THREE.BufferGeometry[] = [];
  const mediumMaterials = new Map<THREE.MeshStandardMaterial, THREE.MeshStandardMaterial>();
  void new GLTFLoader().loadAsync(url).then(({ scene }) => {
    if (!alive) { disposeOwnedGltf(scene); return; }
    const sources: { target: ProductLod; coarse: THREE.Mesh; fine: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial> }[] = [];
    for (const { lod, name } of targets) {
      const coarse = scene.getObjectByName(`${name}-coarse`);
      const fine = scene.getObjectByName(`${name}-fine`);
      if (!(coarse instanceof THREE.Mesh) || !(fine instanceof THREE.Mesh) || !(fine.material instanceof THREE.MeshStandardMaterial)) {
        disposeOwnedGltf(scene);
        return;
      }
      sources.push({ target: lod, coarse, fine: fine as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial> });
    }
    owned = scene;
    scene.updateMatrixWorld(true);
    for (const { target, coarse, fine } of sources) {
      const detailed = target.mesh.geometry === target.fine;
      // Nodes may share source buffers with different transforms; bake private
      // copies so one displayed format cannot deform another.
      target.coarse = coarse.geometry.clone().applyMatrix4(coarse.matrixWorld);
      target.fine = fine.geometry.clone().applyMatrix4(fine.matrixWorld);
      geometries.push(target.coarse, target.fine);
      let material = fine.material;
      if (cheap) {
        let medium = mediumMaterials.get(material);
        if (!medium) {
          medium = material.clone();
          // The owning glTF retains unused source maps for cleanup.
          medium.normalMap = medium.roughnessMap = medium.metalnessMap = null;
          medium.roughness = 0.55;
          mediumMaterials.set(material, medium);
        }
        material = medium;
      }
      target.mesh.geometry = detailed ? target.fine : target.coarse;
      target.mesh.material = material;
      target.mesh.userData.scannedProduce = true;
    }
    onReady?.();
  }).catch(() => { /* Keep the procedural fallback when the scan cannot load. */ });

  return () => {
    if (!alive) return;
    alive = false;
    for (const fallback of fallbacks) {
      const target = fallback.lod;
      const detailed = target.mesh.geometry === target.fine;
      target.coarse = fallback.coarse;
      target.fine = fallback.fine;
      target.mesh.geometry = detailed ? target.fine : target.coarse;
      target.mesh.material = fallback.material;
      delete target.mesh.userData.scannedProduce;
    }
    geometries.forEach((geometry) => geometry.dispose());
    mediumMaterials.forEach((material) => material.dispose());
    if (owned) disposeOwnedGltf(owned);
  };
}
