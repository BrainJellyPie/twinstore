import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { attachPlanarReflection } from "./planarReflection";
import { frameGate } from "./frameGate";

interface Props {
  width: number;
  depth: number;
  map: THREE.Texture;
  roughnessMap: THREE.Texture;
  // Real planar reflections (high quality); otherwise env-map gloss only.
  reflections: boolean;
}

const noRaycast = () => undefined;

export function ReflectiveFloor({ width, depth, map, roughnessMap, reflections }: Props) {
  const ref = useRef<THREE.Mesh>(null);
  const { material, reflection } = useMemo(() => {
    const m = new THREE.MeshStandardMaterial({
      map,
      roughnessMap,
      roughness: 1,
      metalness: 0,
      envMapIntensity: 0.7,
    });
    return { material: m, reflection: reflections ? attachPlanarReflection(m) : null };
  }, [map, roughnessMap, reflections]);

  useEffect(
    () => () => {
      material.dispose();
      reflection?.dispose();
    },
    [material, reflection],
  );

  useFrame((state) => {
    if (!reflection || frameGate.busy()) return;
    reflection.update(state.gl, state.scene, state.camera, ref.current);
  });

  return (
    <mesh
      ref={ref}
      name="realistic-floor"
      position={[width / 2, 0, depth / 2]}
      rotation={[-Math.PI / 2, 0, 0]}
      material={material}
      receiveShadow
      raycast={noRaycast}
    >
      <planeGeometry args={[width, depth]} />
    </mesh>
  );
}
