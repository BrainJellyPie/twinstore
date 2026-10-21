// A procedural store interior to light and reflect the realistic store: rows of LED ceiling panels,
// a bright storefront window on one side, warm floor bounce and colourful stocked walls. Prefiltered
// once (PMREM) it gives glass, chrome and the glossy floor the long light-strip highlights of a real
// shop instead of the neutral grey studio of RoomEnvironment.

import * as THREE from "three";

function box(w: number, h: number, d: number, material: THREE.Material, x: number, y: number, z: number): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  mesh.position.set(x, y, z);
  return mesh;
}

export function createStoreEnvironmentScene(): THREE.Scene {
  const scene = new THREE.Scene();
  const W = 22;
  const D = 16;
  const H = 6;

  // Shell: slightly warm walls and floor, cool white ceiling, rendered from the inside.
  const shell = new THREE.Mesh(
    new THREE.BoxGeometry(W, H, D),
    [
      new THREE.MeshStandardMaterial({ color: "#d9d6cf", side: THREE.BackSide, roughness: 1 }), // +x
      new THREE.MeshStandardMaterial({ color: "#d4d1ca", side: THREE.BackSide, roughness: 1 }), // -x
      new THREE.MeshStandardMaterial({ color: "#f2f3f4", side: THREE.BackSide, roughness: 1 }), // ceiling
      new THREE.MeshStandardMaterial({ color: "#a39d93", side: THREE.BackSide, roughness: 1 }), // floor
      new THREE.MeshStandardMaterial({ color: "#d8d5ce", side: THREE.BackSide, roughness: 1 }), // +z
      new THREE.MeshStandardMaterial({ color: "#d8d5ce", side: THREE.BackSide, roughness: 1 }), // -z
    ],
  );
  shell.position.y = H / 2 - 1;
  scene.add(shell);

  // LED panel rows on the ceiling (the highlights that streak across glass and floor).
  const panel = new THREE.MeshBasicMaterial({ color: new THREE.Color("#ffffff").multiplyScalar(9) });
  for (let row = -2; row <= 2; row++) {
    for (let col = -3; col <= 3; col++) {
      scene.add(box(2.2, 0.05, 0.42, panel, col * 3, H - 1.06, row * 3));
    }
  }

  // Storefront glazing: daylight from one side.
  const daylight = new THREE.MeshBasicMaterial({ color: new THREE.Color("#dfeeff").multiplyScalar(3.2) });
  scene.add(box(0.05, 2.6, D * 0.8, daylight, -W / 2 + 0.1, 1.2, 0));

  // Stocked walls: saturated product colour blocks at shelf height.
  const colors = ["#c6402f", "#2f6fc6", "#e2b23a", "#3f9b57", "#8a4fc0", "#e06d2c", "#2fa7b8"];
  for (let i = 0; i < 14; i++) {
    const m = new THREE.MeshStandardMaterial({ color: colors[i % colors.length], roughness: 0.8 });
    const x = -W / 2 + 2 + i * 1.4;
    scene.add(box(1.2, 1.4, 0.3, m, x, 0.4, D / 2 - 0.4));
    scene.add(box(1.2, 1.4, 0.3, m, x, 0.4, -D / 2 + 0.4));
  }

  // Fridge wall glow.
  const fridge = new THREE.MeshBasicMaterial({ color: new THREE.Color("#e8f6ff").multiplyScalar(1.8) });
  scene.add(box(0.05, 1.8, 6, fridge, W / 2 - 0.1, 0.6, -2));

  scene.add(new THREE.HemisphereLight("#ffffff", "#9a9184", 1.2));
  return scene;
}

export function disposeScene(scene: THREE.Scene): void {
  scene.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    m.geometry.dispose();
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    for (const mat of mats) mat.dispose();
  });
}
