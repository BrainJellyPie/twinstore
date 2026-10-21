import { useEffect, useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { clone as cloneSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";
import { applyShadows } from "@/shared/utils/shadows";
import { bottomAlignOffset, computeBbox, type BboxResult } from "@/shared/utils/glbHelpers";

interface UseGlbModelOptions {
  skinned?: boolean;
  castShadow?: boolean;
  receiveShadow?: boolean;
  overrideMap?: THREE.Texture | null;
}

export interface GlbModelResult {
  clone: THREE.Object3D;
  bbox: BboxResult;
  offset: THREE.Vector3; // bottom-align + x/z center
  animations: THREE.AnimationClip[];
}

// Scale is per-use-site — caller computes from bbox.size.
export function useGlbModel(url: string, opts: UseGlbModelOptions = {}): GlbModelResult {
  const { scene, animations } = useGLTF(url);
  const skinned = opts.skinned ?? false;
  const castShadow = opts.castShadow ?? true;
  const receiveShadow = opts.receiveShadow ?? true;
  const overrideMap = opts.overrideMap ?? null;

  const model = useMemo(() => {
    const clone = skinned ? cloneSkinned(scene) : scene.clone(true);
    applyShadows(clone, castShadow, receiveShadow);
    const owned = new Map<THREE.Material, THREE.Material>();
    if (overrideMap) {
      const overrideMaterial = (source: THREE.Material): THREE.Material => {
        if (!("map" in source) || !(source.map instanceof THREE.Texture)) return source;
        const existing = owned.get(source);
        if (existing) return existing;
        const material = source.clone();
        if ("map" in material) material.map = overrideMap;
        material.needsUpdate = true;
        owned.set(source, material);
        return material;
      };
      clone.traverse((obj) => {
        if (!(obj instanceof THREE.Mesh)) return;
        obj.material = Array.isArray(obj.material)
          ? obj.material.map(overrideMaterial)
          : overrideMaterial(obj.material);
      });
    }
    clone.updateMatrixWorld(true);
    const bbox = computeBbox(clone);
    const offset = bottomAlignOffset(bbox);
    return { clone, bbox, offset, animations, ownedMaterials: [...owned.values()] };
  }, [scene, animations, skinned, castShadow, receiveShadow, overrideMap]);

  useEffect(() => () => {
    // Geometry and textures belong to the GLTF/texture caches; only these copies are ours.
    for (const material of model.ownedMaterials) material.dispose();
  }, [model]);

  return model;
}
