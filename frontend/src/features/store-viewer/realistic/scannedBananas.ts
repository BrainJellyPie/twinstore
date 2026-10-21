import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { disposeOwnedGltf } from "./gltfResources";
import type { ProductLod } from "./productMeshes";

export function loadScannedBananas(target: ProductLod, cheap: boolean, onReady?: () => void): () => void {
  const fallback = { coarse: target.coarse, fine: target.fine, material: target.mesh.material };
  let alive = true;
  let owned: THREE.Group | null = null;
  let mediumMaterial: THREE.MeshStandardMaterial | null = null;
  void new GLTFLoader().loadAsync("/assets/produce/bananas.glb").then(({ scene }) => {
    if (!alive) { disposeOwnedGltf(scene); return; }
    const coarse = scene.getObjectByName("bananas-coarse");
    const fine = scene.getObjectByName("bananas-fine");
    if (!(coarse instanceof THREE.Mesh) || !(fine instanceof THREE.Mesh) || !(fine.material instanceof THREE.MeshStandardMaterial)) {
      disposeOwnedGltf(scene);
      return;
    }
    owned = scene;
    scene.updateMatrixWorld(true);
    coarse.geometry.applyMatrix4(coarse.matrixWorld);
    fine.geometry.applyMatrix4(fine.matrixWorld);
    const detailed = target.mesh.geometry === target.fine;
    target.coarse = coarse.geometry;
    target.fine = fine.geometry;
    let material = fine.material;
    if (cheap) {
      mediumMaterial = material.clone();
      // Keep all source maps on the owning glTF so cleanup can still find them.
      mediumMaterial.normalMap = mediumMaterial.roughnessMap = mediumMaterial.metalnessMap = null;
      mediumMaterial.roughness = 0.55;
      material = mediumMaterial;
    }
    target.mesh.geometry = detailed ? target.fine : target.coarse;
    target.mesh.material = material;
    target.mesh.userData.scannedProduce = true;
    onReady?.();
  }).catch(() => { /* Keep the curved fallback when the scan cannot load. */ });

  return () => {
    if (!alive) return;
    alive = false;
    const detailed = target.mesh.geometry === target.fine;
    target.coarse = fallback.coarse;
    target.fine = fallback.fine;
    target.mesh.geometry = detailed ? target.fine : target.coarse;
    target.mesh.material = fallback.material;
    delete target.mesh.userData.scannedProduce;
    mediumMaterial?.dispose();
    if (owned) disposeOwnedGltf(owned);
  };
}
