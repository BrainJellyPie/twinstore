import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { QUALITY_PRESETS, type GraphicsQuality } from "./constants";
import { personaRegistry } from "./personaRegistry";
import { acquireRoomEnvironment, releaseRoomEnvironment, retainRoomEnvironment } from "./envCache";

interface Props {
  width: number;
  depth: number;
  quality: GraphicsQuality;
  // Night-shift theme: slightly cooler, dimmer light.
  dark: boolean;
}

// Store lighting: procedural store interior (storeEnvironment → PMREM, no
// HDR downloads) for reflections and soft fill, a high key light standing in for
// the ceiling panels (soft PCF shadows), and a warm/cool hemisphere bounce.
// On "medium" the environment is applied only to small metal/glass parts
// (RealisticStore) — sampling it on every wall and floor pixel is the single
// most expensive term under software GL — and the hemisphere/ambient fill
// takes over its diffuse share.
export function RealisticLighting({ width, depth, quality, dark }: Props) {
  const get = useThree((s) => s.get);
  const preset = QUALITY_PRESETS[quality];

  const env = useMemo(() => acquireRoomEnvironment(get().gl), [get]);
  useEffect(() => {
    const { gl, scene } = get();
    retainRoomEnvironment(gl);
    const prev = {
      environment: scene.environment,
      intensity: scene.environmentIntensity,
      exposure: gl.toneMappingExposure,
      toneMapping: gl.toneMapping,
    };
    // Khronos PBR Neutral keeps package colours true (ACES shifts reds to orange and blues to cyan).
    gl.toneMapping = THREE.NeutralToneMapping;
    return () => {
      scene.environment = prev.environment;
      scene.environmentIntensity = prev.intensity;
      gl.toneMappingExposure = prev.exposure;
      gl.toneMapping = prev.toneMapping;
      releaseRoomEnvironment(gl);
    };
  }, [get]);

  const fullEnv = quality === "high";
  useEffect(() => {
    const { gl, scene } = get();
    scene.environment = fullEnv ? env : null;
    scene.environmentIntensity = dark ? 0.5 : 0.62;
    gl.toneMappingExposure = dark ? 0.9 : 0.98;
  }, [get, dark, env, fullEnv]);

  // Shadow-map throttling: the store is static, so the map is redrawn only
  // every few frames while shoppers move (and a few times after changes).
  // Pixel ratio is capped per quality.
  const frame = useRef(0);
  const settle = useRef(0);
  useEffect(() => {
    const { gl, setDpr } = get();
    const prevDpr = gl.getPixelRatio();
    setDpr(Math.min(window.devicePixelRatio || 1, preset.dprMax));
    gl.shadowMap.autoUpdate = preset.shadowEvery <= 1;
    gl.shadowMap.needsUpdate = true;
    settle.current = 30;
    return () => {
      gl.shadowMap.autoUpdate = true;
      setDpr(prevDpr);
    };
  }, [get, preset]);
  useFrame(({ gl }) => {
    if (gl.shadowMap.autoUpdate) return;
    frame.current++;
    // A few refreshes after (re)mounts so late-arriving meshes are captured.
    if (settle.current > 0) {
      settle.current--;
      if (settle.current % 10 === 0) gl.shadowMap.needsUpdate = true;
    }
    if (personaRegistry.count > 0 && frame.current % preset.shadowEvery === 0) gl.shadowMap.needsUpdate = true;
  });

  const ext = Math.max(width, depth) / 2 + 3;
  return (
    <>
      <hemisphereLight
        args={dark ? ["#e2e9ff", "#2c3252", fullEnv ? 0.5 : 1.0] : ["#fbfdff", "#d9d2c6", fullEnv ? 0.55 : 1.05]}
      />
      {!fullEnv && <ambientLight intensity={dark ? 0.32 : 0.38} color={dark ? "#e8edff" : "#fffdf8"} />}
      <directionalLight
        key={quality}
        position={[2.5, 12, 4.5]}
        intensity={dark ? 1.9 : 2.1}
        color={dark ? "#f2f5ff" : "#fffaf2"}
        castShadow
        shadow-mapSize={[preset.shadowMapSize, preset.shadowMapSize]}
        shadow-radius={preset.shadowRadius}
        shadow-bias={-0.0003}
        shadow-normalBias={0.015}
        shadow-camera-left={-ext}
        shadow-camera-right={ext}
        shadow-camera-top={ext}
        shadow-camera-bottom={-ext}
        shadow-camera-near={0.5}
        shadow-camera-far={40}
      />
      {/* Low fill from the camera side so shelf fronts read well (high only — one
          light less per pixel matters under software GL). */}
      {quality === "high" && <directionalLight position={[8, 5, 10]} intensity={0.45} color="#eef4ff" />}
    </>
  );
}
