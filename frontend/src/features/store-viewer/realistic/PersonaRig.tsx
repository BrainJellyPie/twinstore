import { useEffect, useRef, type ReactNode } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { PERSONA_SCALE } from "./constants";
import { personaRegistry } from "./personaRegistry";

interface Props {
  realistic: boolean;
  children: ReactNode;
}

// Wraps the playback personas (whose components are shared with Classic mode):
// publishes their live positions, scales them to adult height and hides the
// persona whose eyes the shopper-view camera is using. Photographic avatars
// keep their authored skin, cloth and hair materials.
export function PersonaRig({ realistic, children }: Props) {
  const root = useRef<THREE.Group>(null);

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

  useEffect(
    () => () => {
      personaRegistry.count = 0;
      personaRegistry.hideNear = null;
    },
    [],
  );

  return <group ref={root}>{children}</group>;
}
