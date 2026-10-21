// Photo mode: the current view of the realistic store, path traced (three-gpu-pathtracer) into a
// photoreal still — global illumination, area-light shadows, glossy floor and glass — that refines
// sample by sample and can be saved as a PNG. Moving the camera restarts the accumulation.

import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { HDRLoader } from "three/examples/jsm/loaders/HDRLoader.js";
import { DenoiseMaterial, WebGLPathTracer } from "three-gpu-pathtracer";
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
    let renderPhoto: (() => void) | null = null;
    usePlaybackControlStore.getState().pause();
    let alive = true;
    let pathTracer: WebGLPathTracer | null = null;
    let worker: GenerateMeshBVHWorker | null = null;
    let disposeScene: (() => void) | null = null;
    let disposeDenoise: (() => void) | null = null;
    let saved = usePhotoMode.getState().saveRequest;
    const signature = new Float64Array(32);

    // Let the HUD paint "Building…" before the main thread is busy baking geometry.
    const timer = window.setTimeout(async () => {
      try {
        const background = scene.background instanceof THREE.Color ? scene.background.clone() : null;
        const environment = await new HDRLoader().loadAsync("/assets/environments/gear_store_1k.hdr").catch(() => null);
        if (!alive || usePhotoMode.getState().status === "off") {
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
        pt.filterGlossyFactor = 1;
        pt.minSamples = 1;
        pt.fadeDuration = 0;
        pt.dynamicLowRes = true;
        pt.lowResScale = 0.25;
        pt.rasterizeScene = false;
        // Smart denoise on the final blit; it tone-maps itself, like the default blit.
        const denoise = new DenoiseMaterial({
          map: pt.target.texture, blending: THREE.NoBlending, premultipliedAlpha: gl.getContextAttributes()?.premultipliedAlpha ?? true,
        });
        disposeDenoise = () => denoise.dispose();
        pt.renderToCanvasCallback = (target, renderer, quad) => {
          const autoClear = renderer.autoClear;
          renderer.autoClear = false;
          const { denoise: on } = usePhotoMode.getState();
          if (on && pt.samples >= 1) {
            const blit = quad.material;
            denoise.map = target.texture;
            // Few samples: noise exceeds a small edge threshold and would be kept as detail.
            denoise.sigma = pt.samples < 32 ? 5 : pt.samples < 128 ? 4 : 2.5;
            denoise.threshold = pt.samples < 32 ? 0.18 : pt.samples < 128 ? 0.1 : 0.05;
            quad.material = denoise;
            quad.render(renderer);
            quad.material = blit;
          } else {
            quad.render(renderer);
          }
          renderer.autoClear = autoClear;
        };
        usePhotoMode.setState({ triangles: photo.triangles });
        await pt.setSceneAsync(photo.scene, get().camera, { onProgress: (p) => { if (alive) usePhotoMode.setState({ progress: p }); } });
        if (!alive || usePhotoMode.getState().status === "off") return;
        usePhotoMode.setState({ status: "tracing", samples: 0 });
        renderPhoto = () => {
          // Zustand changes synchronously; React's effect cleanup can run after
          // the next frame. A queued draw must not resurrect a stopped photo.
          const state = usePhotoMode.getState();
          if (!alive || state.status === "off") return;
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
        frameGate.photoRenderer = renderPhoto;
      } catch (e) {
        if (alive && usePhotoMode.getState().status !== "off") usePhotoMode.setState({ status: "error", error: e instanceof Error ? e.message : String(e) });
      }
    }, 60);

    return () => {
      alive = false;
      window.clearTimeout(timer);
      if (frameGate.photoRenderer === renderPhoto) frameGate.photoRenderer = null;
      pathTracer?.dispose();
      worker?.dispose();
      disposeDenoise?.();
      disposeScene?.();
    };
  }, [active, get, width, depth]);

  return null;
}
