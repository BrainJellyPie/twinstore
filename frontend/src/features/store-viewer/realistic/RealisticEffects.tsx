import { useEffect, useMemo } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { GTAOPass } from "three/examples/jsm/postprocessing/GTAOPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { frameGate } from "./frameGate";

// High-quality post stack: ground-truth AO + gentle bloom on the LED strips and
// ceiling panels. Plugs into the GatedRenderer while mounted.
export function RealisticEffects() {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const dpr = useThree((s) => s.viewport.dpr);

  const composer = useMemo(() => {
    const w = Math.max(1, Math.round(size.width * dpr));
    const h = Math.max(1, Math.round(size.height * dpr));
    const rt = new THREE.WebGLRenderTarget(w, h, { type: THREE.HalfFloatType, samples: 4 });
    const c = new EffectComposer(gl, rt);
    c.setPixelRatio(dpr);
    c.setSize(size.width, size.height);
    c.addPass(new RenderPass(scene, camera));
    const ao = new GTAOPass(scene, camera, w, h);
    ao.output = GTAOPass.OUTPUT.Default;
    ao.blendIntensity = 0.85;
    ao.updateGtaoMaterial({ radius: 0.35, distanceExponent: 1.4, thickness: 1.2, scale: 1.0, samples: 12 });
    c.addPass(ao);
    // HDR threshold well above lit white surfaces: only LED strips / panels bloom.
    c.addPass(new UnrealBloomPass(new THREE.Vector2(w / 2, h / 2), 0.16, 0.22, 4.0));
    c.addPass(new OutputPass());
    return c;
  }, [gl, scene, camera, size.width, size.height, dpr]);

  useEffect(() => {
    frameGate.renderer = (delta) => composer.render(delta);
    return () => {
      frameGate.renderer = null;
      // EffectComposer owns its ping-pong targets, but each pass owns the AO,
      // bloom and output buffers. Release those on quality changes and resize.
      for (const pass of composer.passes) {
        pass.dispose();
        // Three r183 leaves these two shader materials out of pass.dispose().
        if (pass instanceof GTAOPass) pass.gtaoMaterial.dispose();
        if (pass instanceof UnrealBloomPass) pass.materialHighPassFilter.dispose();
      }
      composer.dispose();
    };
  }, [composer]);

  return null;
}
