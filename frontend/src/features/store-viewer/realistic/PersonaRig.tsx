import { useEffect, useRef, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { PERSONA_SCALE } from "./constants";
import { personaRegistry } from "./personaRegistry";

interface Props {
  realistic: boolean;
  children: ReactNode;
}

interface SavedMaterial {
  roughness: number;
  envMapIntensity: number;
}

// Wraps the playback personas (whose components are shared with Classic mode):
// publishes their live positions, scales them to adult height and gives their
// materials a satin finish in Realistic mode, and hides the persona whose eyes
// the shopper-view camera is using.
export function PersonaRig({ realistic, children }: Props) {
  const root = useRef<THREE.Group>(null);
  const saved = useRef(new Map<THREE.MeshStandardMaterial, SavedMaterial>());

  useFrame(() => {
    const g = root.current;
    if (!g) return;
    const scale = realistic ? PERSONA_SCALE : 1;
    let n = 0;
    for (const child of g.children) {
      // Persona bodies are plain groups; trails are Line2 meshes.
      if (child.type !== "Group") continue;
      if (child.scale.x !== scale) child.scale.setScalar(scale);
      personaRegistry.xs[n] = child.position.x;
      personaRegistry.zs[n] = child.position.z;
      n++;
      if (realistic && !child.userData.realisticTuned) {
        child.userData.realisticTuned = true;
        child.traverse((o) => {
          const mesh = o as THREE.Mesh;
          if (!mesh.isMesh) return;
          mesh.castShadow = true;
          const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          for (const m of mats) {
            const sm = m as THREE.MeshStandardMaterial;
            if (!sm.isMeshStandardMaterial || saved.current.has(sm)) continue;
            saved.current.set(sm, { roughness: sm.roughness, envMapIntensity: sm.envMapIntensity });
            sm.roughness = 0.62;
            sm.envMapIntensity = 0.85;
          }
        });
      } else if (!realistic && child.userData.realisticTuned) {
        child.userData.realisticTuned = false;
      }
    }
    personaRegistry.count = n;

    // Hide the followed persona (camera sits in its head).
    const hide = personaRegistry.hideNear;
    for (const child of g.children) {
      if (child.type !== "Group") continue;
      let visible = true;
      if (hide) {
        const dx = child.position.x - hide.x;
        const dz = child.position.z - hide.z;
        // Everyone within arm's reach of the eyes (queues overlap on a tile).
        visible = dx * dx + dz * dz > 0.6 * 0.6;
      }
      if (child.visible !== visible) child.visible = visible;
    }
  });

  // Leaving Realistic mode: restore the shared GLB materials.
  useEffect(() => {
    if (realistic) return;
    const map = saved.current;
    for (const [m, v] of map) {
      m.roughness = v.roughness;
      m.envMapIntensity = v.envMapIntensity;
    }
    map.clear();
  }, [realistic]);

  useEffect(
    () => () => {
      personaRegistry.count = 0;
      personaRegistry.hideNear = null;
    },
    [],
  );

  return <group ref={root}>{children}</group>;
}
