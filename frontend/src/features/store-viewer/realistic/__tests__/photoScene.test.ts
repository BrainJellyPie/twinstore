import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { buildPhotoScene } from "../photoScene";
import { CEILING_HEIGHT } from "../constants";

describe("photo scene snapshots", () => {
  it("leaves shared live geometry unchanged across repeated photos", () => {
    const live = new THREE.Scene();
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial();
    const first = new THREE.Mesh(geometry, material);
    first.position.set(-2, 0, -3);
    first.rotation.y = Math.PI / 3;
    const second = new THREE.Mesh(geometry, material);
    second.position.set(2, 0, 3);
    live.add(first, second);
    const originalPositions = Array.from(geometry.getAttribute("position").array);
    const originalNormals = Array.from(geometry.getAttribute("normal").array);
    const disposed = vi.fn();
    geometry.addEventListener("dispose", disposed);

    const snapshots: number[][] = [];
    for (let i = 0; i < 2; i++) {
      const photo = buildPhotoScene(live, { width: 4, depth: 6, background: null });
      const mesh = photo.scene.children.find((o) => o instanceof THREE.Mesh) as THREE.Mesh;
      snapshots.push(Array.from(mesh.geometry.getAttribute("position").array));
      photo.dispose();
      expect(Array.from(geometry.getAttribute("position").array)).toEqual(originalPositions);
      expect(Array.from(geometry.getAttribute("normal").array)).toEqual(originalNormals);
      expect(disposed).not.toHaveBeenCalled();
    }
    expect(snapshots[0]).toEqual(snapshots[1]);
    geometry.dispose();
    material.dispose();
  });

  it("places photo lights under the ceiling panels in the centered store", () => {
    const photo = buildPhotoScene(new THREE.Scene(), { width: 4, depth: 5, background: null });
    photo.scene.updateMatrixWorld(true);
    const lights: THREE.RectAreaLight[] = [];
    photo.scene.traverse((o) => { if (o instanceof THREE.RectAreaLight) lights.push(o); });
    expect(lights).toHaveLength(10);
    expect(lights[0]!.getWorldPosition(new THREE.Vector3()).toArray()).toEqual([-1.5, CEILING_HEIGHT - 0.02, -2]);
    expect(lights[0]!.width).toBe(0.46);
    expect(lights[0]!.height).toBe(0.46);
    for (const light of lights) {
      expect(Math.abs(light.position.x)).toBeLessThan(2);
      expect(Math.abs(light.position.z)).toBeLessThan(2.5);
      expect(new THREE.Vector3(0, 0, 1).applyQuaternion(light.quaternion).y).toBeCloseTo(1);
    }
    photo.dispose();
  });

  it("bakes a shopper's current eyelid deformation without changing its live morph state", () => {
    const geometry = new THREE.PlaneGeometry(1, 1);
    const count = geometry.getAttribute("position").count;
    const deltas = new Float32Array(count * 3);
    const weights = new Float32Array(count * 4);
    for (let i = 0; i < count; i++) { deltas[i * 3 + 1] = -0.02; weights[i * 4] = 1; }
    geometry.morphAttributes.position = [new THREE.BufferAttribute(deltas, 3)];
    geometry.morphTargetsRelative = true;
    geometry.setAttribute("skinIndex", new THREE.Uint16BufferAttribute(new Uint16Array(count * 4), 4));
    geometry.setAttribute("skinWeight", new THREE.BufferAttribute(weights, 4));
    const material = new THREE.MeshStandardMaterial();
    const mesh = new THREE.SkinnedMesh(geometry, material);
    const bone = new THREE.Bone();
    mesh.add(bone);
    mesh.bind(new THREE.Skeleton([bone]));
    mesh.position.set(2, 3, -1);
    mesh.morphTargetInfluences![0] = 0.75;
    const live = new THREE.Scene();
    live.add(mesh);
    live.updateMatrixWorld(true);
    mesh.skeleton.update();
    const expected = mesh.getVertexPosition(0, new THREE.Vector3()).applyMatrix4(mesh.matrixWorld);
    const photo = buildPhotoScene(live, { width: 4, depth: 5, background: null });
    const baked = photo.scene.children.find((o) => o instanceof THREE.Mesh) as THREE.Mesh;
    const vertex = new THREE.Vector3().fromBufferAttribute(baked.geometry.getAttribute("position"), 0);
    expect(vertex.distanceTo(expected)).toBeLessThan(1e-6);
    expect(mesh.morphTargetInfluences![0]).toBe(0.75);
    expect(geometry.getAttribute("position").getY(0)).toBe(0.5);
    photo.dispose();
    geometry.dispose();
    material.dispose();
    mesh.skeleton.dispose();
  });
});
