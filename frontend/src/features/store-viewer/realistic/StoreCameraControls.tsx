import { useEffect, useMemo, useRef, useState, type ComponentRef } from "react";
import { useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { OrthographicCamera } from "three";
import { usePhotoMode } from "./photoModeStore";
import { storeCameraFit } from "./storeCameraFit";

interface Props {
  // While the shopper view owns the default camera the isometric controls idle.
  disabled: boolean;
  maxZoom?: number;
  width: number;
  depth: number;
  fitRequest: number;
}

// Pan/zoom controls bound to the canvas' original (isometric) camera, so they
// keep their state while another camera is temporarily the default.
export function StoreCameraControls({ disabled, maxZoom = 140, width, depth, fitRequest }: Props) {
  const get = useThree((s) => s.get);
  const size = useThree((s) => s.size);
  const invalidate = useThree((s) => s.invalidate);
  const [isoCamera] = useState(() => get().camera);
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const lastFit = useRef("");
  const photoActive = usePhotoMode((s) => s.status !== "off");
  const fit = useMemo(() => storeCameraFit(width, depth, size.width, size.height, maxZoom), [width, depth, size.width, size.height, maxZoom]);
  const fitKey = `${width}:${depth}:${size.width}:${size.height}:${fitRequest}`;
  useEffect(() => {
    // Returning from a temporary camera must preserve the user's pan and zoom.
    if (disabled || photoActive || lastFit.current === fitKey) return;
    const orbit = controls.current;
    if (!orbit || size.width <= 0 || size.height <= 0) return;
    const camera = orbit.object;
    if (!(camera instanceof OrthographicCamera)) return;
    const damping = orbit.enableDamping;
    orbit.enableDamping = false;
    orbit.update(); // Finish any pending pan before replacing the view.
    orbit.enableDamping = damping;
    orbit.target.copy(fit.target);
    camera.position.copy(fit.position);
    camera.zoom = fit.zoom;
    camera.lookAt(fit.target);
    camera.updateProjectionMatrix();
    orbit.update();
    lastFit.current = fitKey;
    invalidate();
  }, [disabled, photoActive, fitKey, fit, invalidate, size.width, size.height]);
  return (
    <OrbitControls
      ref={controls}
      camera={isoCamera}
      enabled={!disabled}
      enableRotate={false}
      enablePan
      enableZoom
      minZoom={Math.min(20, fit.zoom / 2)}
      maxZoom={maxZoom}
    />
  );
}
