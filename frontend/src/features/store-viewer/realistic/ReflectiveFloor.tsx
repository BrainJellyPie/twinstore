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
  normalMap: THREE.Texture | null;
  // Real planar reflections (high quality); otherwise env-map gloss only.
  reflections: boolean;
  color?: string;
}

const noRaycast = () => undefined;

export function ReflectiveFloor({ width, depth, map, roughnessMap, normalMap, reflections, color = "#ffffff" }: Props) {
  const ref = useRef<THREE.Mesh>(null);
  const { material, reflection } = useMemo(() => {
    const m = new THREE.MeshStandardMaterial({
      color,
      map,
      roughnessMap,
      normalMap,
      normalScale: new THREE.Vector2(0.45, 0.45),
      roughness: 1,
      metalness: 0,
      envMapIntensity: 0.7,
    });
    return { material: m, reflection: reflections ? attachPlanarReflection(m) : null };
  }, [map, roughnessMap, normalMap, reflections, color]);

  useEffect(
    () => () => {
      material.dispose();
      reflection?.dispose();
    },
    [material, reflection],
  );

  useFrame((state) => {
    // The path tracer computes its own reflections; skip the live mirror pass.
    if (!reflection || frameGate.photoRenderer || frameGate.busy()) return;
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
