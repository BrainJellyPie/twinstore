// Photo mode: the current view of the realistic store, path traced (three-gpu-pathtracer) into a
// photoreal still — global illumination, area-light shadows, glossy floor and glass — that refines
// sample by sample and can be saved as a PNG. Moving the camera restarts the accumulation.

import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { HDRLoader } from "three/examples/jsm/loaders/HDRLoader.js";
import { WebGLPathTracer } from "three-gpu-pathtracer";
import { GenerateMeshBVHWorker } from "three-mesh-bvh/worker";

import { usePlaybackControlStore } from "@/stores/playbackControlStore";

import { frameGate } from "./frameGate";
import { buildPhotoScene } from "./photoScene";
import { usePhotoMode } from "./photoModeStore";

function download(url: string) {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  const a = Object.assign(document.createElement("a"), { href: url, download: `twinstore-photo-${stamp}.png` });
  a.click();
}

export function PhotoMode({ width, depth }: { width: number; depth: number }) {
  const active = usePhotoMode((s) => s.status !== "off");
  const get = useThree((s) => s.get);

  useEffect(() => {
    if (!active) return;
    const { gl, scene } = get();
    const previous = frameGate.renderer;
    usePlaybackControlStore.getState().pause();
    let alive = true;
    let pathTracer: WebGLPathTracer | null = null;
    let worker: GenerateMeshBVHWorker | null = null;
    let disposeScene: (() => void) | null = null;
    let saved = usePhotoMode.getState().saveRequest;
    const signature = new Float64Array(32);

    // Let the HUD paint "Building…" before the main thread is busy baking geometry.
    const timer = window.setTimeout(async () => {
      try {
        const background = scene.background instanceof THREE.Color ? scene.background.clone() : null;
        const environment = await new HDRLoader().loadAsync("/assets/environments/gear_store_1k.hdr").catch(() => null);
        if (!alive) {
          environment?.dispose();
          return;
        }
        if (environment) environment.mapping = THREE.EquirectangularReflectionMapping;
        const photo = buildPhotoScene(scene, { width, depth, background, environment });
        disposeScene = photo.dispose;
        const pt = new WebGLPathTracer(gl);
        pathTracer = pt;
        // The BVH over the whole store is built off the main thread.
        worker = new GenerateMeshBVHWorker();
        pt.setBVHWorker(worker);
        pt.renderScale = Math.min(1, 1.5 / gl.getPixelRatio());
        pt.tiles.set(2, 2);
        pt.bounces = 5;
        pt.transmissiveBounces = 8;
        pt.filterGlossyFactor = 0.5;
        pt.minSamples = 1;
        pt.fadeDuration = 0;
        pt.dynamicLowRes = true;
        pt.lowResScale = 0.25;
        pt.rasterizeScene = false;
        usePhotoMode.setState({ triangles: photo.triangles });
        await pt.setSceneAsync(photo.scene, get().camera, { onProgress: (p) => usePhotoMode.setState({ progress: p }) });
        if (!alive) return;
        usePhotoMode.setState({ status: "tracing", samples: 0 });
        frameGate.renderer = () => {
          const camera = get().camera;
          const m = camera.matrixWorld.elements;
          const p = camera.projectionMatrix.elements;
          let moved = false;
          for (let i = 0; i < 16; i++) {
            if (signature[i] !== m[i] || signature[16 + i] !== p[i]) moved = true;
            signature[i] = m[i]!;
            signature[16 + i] = p[i]!;
          }
          if (moved) {
            if (pt.camera !== camera) pt.setCamera(camera);
            else pt.updateCamera();
          }
          const state = usePhotoMode.getState();
          pt.pausePathTracing = pt.samples >= state.target;
          pt.renderSample();
          const samples = Math.floor(pt.samples);
          const status = samples >= state.target ? "done" : "tracing";
          if (samples !== state.samples || status !== state.status) usePhotoMode.setState({ samples, status });
          // Read the canvas in the frame that drew it (the drawing buffer is not preserved).
          if (state.saveRequest !== saved) {
            saved = state.saveRequest;
            download(gl.domElement.toDataURL("image/png"));
          }
        };
      } catch (e) {
        if (alive) usePhotoMode.setState({ status: "error", error: e instanceof Error ? e.message : String(e) });
      }
    }, 60);

    return () => {
      alive = false;
      window.clearTimeout(timer);
      frameGate.renderer = previous;
      pathTracer?.dispose();
      worker?.dispose();
      disposeScene?.();
    };
  }, [active, get, width, depth]);

  return null;
}
