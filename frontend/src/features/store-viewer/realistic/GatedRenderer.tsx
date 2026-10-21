import { useEffect } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { frameGate } from "./frameGate";

// Takes over R3F's render (priority 1) and draws a frame only when the GPU has
// finished the previous one — see frameGate.ts. Simulation callbacks (priority
// 0) still run every animation frame.
export function GatedRenderer() {
  const get = useThree((s) => s.get);

  useEffect(() => {
    frameGate.attach(get().gl.getContext() as WebGL2RenderingContext);
    return () => frameGate.detach();
  }, [get]);

  useFrame((state, delta) => {
    if (frameGate.busy()) return;
    frameGate.begin();
    try {
      const render = frameGate.photoRenderer ?? frameGate.renderer;
      if (render) render(delta);
      else state.gl.render(state.scene, state.camera);
    } finally {
      frameGate.end();
    }
  }, 1);

  return null;
}
