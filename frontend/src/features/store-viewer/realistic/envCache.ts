// One prefiltered store environment per renderer (see storeEnvironment.ts), created on first use so
// the lighting and the materials that sample it get the same texture in the same render (no
// material rebuild once the environment "arrives").

import * as THREE from "three";
import { HDRLoader } from "three/examples/jsm/loaders/HDRLoader.js";
import { createStoreEnvironmentScene, disposeScene } from "./storeEnvironment";

interface Entry {
  target: THREE.WebGLRenderTarget;
  photographicTarget?: THREE.WebGLRenderTarget;
  photographic?: Promise<THREE.Texture | null>;
  users: number;
}

const cache = new WeakMap<THREE.WebGLRenderer, Entry>();

export function acquireRoomEnvironment(gl: THREE.WebGLRenderer): THREE.Texture {
  let entry = cache.get(gl);
  if (!entry) {
    const pmrem = new THREE.PMREMGenerator(gl);
    const room = createStoreEnvironmentScene();
    const target = pmrem.fromScene(room, 0.025);
    pmrem.dispose();
    disposeScene(room);
    entry = { target, users: 0 };
    cache.set(gl, entry);
  }
  return entry.target.texture;
}

// High quality uses the measured range and reflections of a real fluorescent-lit
// retail interior. Decode and prefilter once per renderer; retain the procedural
// room as an immediate fallback and for Medium's small reflective parts.
export function acquirePhotographicEnvironment(gl: THREE.WebGLRenderer): Promise<THREE.Texture | null> {
  acquireRoomEnvironment(gl);
  const entry = cache.get(gl)!;
  entry.photographic ??= new HDRLoader().loadAsync("/assets/environments/gear_store_1k.hdr").then((hdr) => {
    // The viewer may have closed while the file was loading.
    if (cache.get(gl) !== entry) {
      hdr.dispose();
      return null;
    }
    const pmrem = new THREE.PMREMGenerator(gl);
    try {
      entry.photographicTarget = pmrem.fromEquirectangular(hdr);
      entry.photographicTarget.texture.name = "Poly Haven · Gear Store";
      return entry.photographicTarget.texture;
    } finally {
      pmrem.dispose();
      hdr.dispose();
    }
  }).catch(() => null);
  return entry.photographic;
}

// Effect-scoped ownership: the texture is disposed once the last holder lets
// go (deferred a tick so StrictMode's unmount/remount does not drop it).
export function retainRoomEnvironment(gl: THREE.WebGLRenderer): void {
  const entry = cache.get(gl);
  if (entry) entry.users++;
}

export function releaseRoomEnvironment(gl: THREE.WebGLRenderer): void {
  const entry = cache.get(gl);
  if (!entry) return;
  entry.users = Math.max(0, entry.users - 1);
  if (entry.users > 0) return;
  setTimeout(() => {
    if (entry.users > 0 || cache.get(gl) !== entry) return;
    cache.delete(gl);
    entry.target.dispose();
    entry.photographicTarget?.dispose();
  }, 0);
}
