import { useState } from "react";
import { useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

interface Props {
  // While the shopper view owns the default camera the isometric controls idle.
  disabled: boolean;
  maxZoom?: number;
}

// Pan/zoom controls bound to the canvas' original (isometric) camera, so they
// keep their state while another camera is temporarily the default.
export function StoreCameraControls({ disabled, maxZoom = 140 }: Props) {
  const get = useThree((s) => s.get);
  const [isoCamera] = useState(() => get().camera);
  return (
    <OrbitControls
      camera={isoCamera}
      enabled={!disabled}
      enableRotate={false}
      target={[0, 0.5, 0]}
      enablePan
      enableZoom
      minZoom={20}
      maxZoom={maxZoom}
    />
  );
}
