// Photo mode: the current view of the realistic store, path traced (three-gpu-pathtracer) into a
// photoreal still — global illumination, area-light shadows, glossy floor and glass — that refines
// sample by sample and can be saved as a PNG. Moving the camera restarts the accumulation.

import { useEffect } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { HDRLoader } from "three/examples/jsm/loaders/HDRLoader.js";
import { DenoiseMaterial, PhysicalCamera, WebGLPathTracer } from "three-gpu-pathtracer";
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
  const active = usePhotoMode((s) => s.status !== "off" && s.status !== "error");
  const get = useThree((s) => s.get);

  // Leaving the 3D view ends photo mode; the shared store would otherwise keep the HUD and camera lock on.
  useEffect(() => () => usePhotoMode.getState().stop(), []);

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
    const signature = new Float64Array(34);

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
        denoise.onBeforeCompile = (shader) => {
          // Compare edges in the displayed colour space. In linear HDR, noise on
          // bright walls can exceed the threshold and be mistaken for detail.
          // Keep the weighted average in linear light to preserve its energy.
          shader.fragmentShader = shader.fragmentShader.replace("vec4 dC = walkPx - centrPx;", `
            vec3 centerColor = centrPx.rgb;
            vec3 neighborColor = walkPx.rgb;
            #ifdef TONE_MAPPING
              centerColor = toneMapping(centerColor);
              neighborColor = toneMapping(neighborColor);
            #endif
            centerColor = linearToOutputTexel(vec4(centerColor, 1.0)).rgb;
            neighborColor = linearToOutputTexel(vec4(neighborColor, 1.0)).rgb;
            vec4 dC = vec4(neighborColor - centerColor, walkPx.a - centrPx.a);
          `);
        };
        disposeDenoise = () => denoise.dispose();
        pt.renderToCanvasCallback = (target, renderer, quad) => {
          const autoClear = renderer.autoClear;
          const blit = quad.material;
          try {
            renderer.autoClear = false;
            const { denoise: on } = usePhotoMode.getState();
            if (on && pt.samples >= 1) {
              denoise.map = target.texture;
              denoise.sigma = pt.samples < 32 ? 4 : pt.samples < 128 ? 3 : 2;
              denoise.threshold = THREE.MathUtils.clamp(1.44 / Math.sqrt(pt.samples), 0.03, 0.3);
              quad.material = denoise;
            }
            quad.render(renderer);
          } finally {
            quad.material = blit;
            renderer.autoClear = autoClear;
          }
        };
        usePhotoMode.setState({ triangles: photo.triangles });
        await pt.setSceneAsync(photo.scene, get().camera, { onProgress: (p) => { if (alive) usePhotoMode.setState({ progress: p }); } });
        if (!alive || usePhotoMode.getState().status === "off") return;
        usePhotoMode.setState({ status: "tracing", samples: 0 });
        // Depth of field: a physical camera that follows the live one and focuses on the frame's centre.
        const lens = new PhysicalCamera();
        lens.apertureBlades = 6;
        const ray = new THREE.Raycaster();
        const centre = new THREE.Vector2(0, 0);
        const drawPhoto = () => {
          // Zustand changes synchronously; React's effect cleanup can run after
          // the next frame. A queued draw must not resurrect a stopped photo.
          const state = usePhotoMode.getState();
          if (!alive || state.status === "off" || state.status === "error") return;
          const camera = get().camera;
          const live = camera as THREE.PerspectiveCamera;
          const perspective = live.isPerspectiveCamera === true;
          if (perspective !== state.perspective) usePhotoMode.setState({ perspective });
          const dof = perspective && state.dof;
          const m = camera.matrixWorld.elements;
          const p = camera.projectionMatrix.elements;
          let moved = signature[32] !== (dof ? 1 : 0) || signature[33] !== state.fStop;
          signature[32] = dof ? 1 : 0;
          signature[33] = state.fStop;
          for (let i = 0; i < 16; i++) {
            if (signature[i] !== m[i] || signature[16 + i] !== p[i]) moved = true;
            signature[i] = m[i]!;
            signature[16 + i] = p[i]!;
          }
          if (moved) {
            let traced: THREE.Camera = camera;
            if (dof) {
              lens.position.copy(live.position);
              lens.quaternion.copy(live.quaternion);
              lens.fov = live.fov;
              lens.aspect = live.aspect;
              lens.near = live.near;
              lens.far = live.far;
              lens.fStop = state.fStop;
              lens.updateProjectionMatrix();
              lens.updateMatrixWorld(true);
              ray.setFromCamera(centre, live);
              const hit = ray.intersectObjects(photo.scene.children, false)[0];
              lens.focusDistance = hit ? hit.distance : 3;
              traced = lens;
            }
            if (pt.camera !== traced) pt.setCamera(traced);
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
        renderPhoto = () => {
          try {
            drawPhoto();
          } catch (e) {
            // A failed draw must not escape into R3F and stop its animation loop.
            // The error state releases photo resources and leaves the live view usable.
            if (frameGate.photoRenderer === renderPhoto) frameGate.photoRenderer = null;
            if (alive && usePhotoMode.getState().status !== "off") {
              usePhotoMode.setState({ status: "error", error: e instanceof Error ? e.message : String(e) });
            }
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
