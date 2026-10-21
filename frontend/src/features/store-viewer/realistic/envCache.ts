// One prefiltered store environment per renderer (see storeEnvironment.ts), created on first use so
// the lighting and the materials that sample it get the same texture in the same render (no
// material rebuild once the environment "arrives").

import * as THREE from "three";
import { createStoreEnvironmentScene, disposeScene } from "./storeEnvironment";

interface Entry {
  texture: THREE.Texture;
  users: number;
}

const cache = new WeakMap<THREE.WebGLRenderer, Entry>();

export function acquireRoomEnvironment(gl: THREE.WebGLRenderer): THREE.Texture {
  let entry = cache.get(gl);
  if (!entry) {
    const pmrem = new THREE.PMREMGenerator(gl);
    const room = createStoreEnvironmentScene();
    const texture = pmrem.fromScene(room, 0.025).texture;
    pmrem.dispose();
    disposeScene(room);
    entry = { texture, users: 0 };
    cache.set(gl, entry);
  }
  return entry.texture;
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
    entry.texture.dispose();
  }, 0);
}
