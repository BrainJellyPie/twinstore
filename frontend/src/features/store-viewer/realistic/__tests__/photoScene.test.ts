import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { buildPhotoScene } from "../photoScene";
import { CEILING_HEIGHT } from "../constants";

describe("photo scene snapshots", () => {
  it("retains instance tints alongside untinted meshes sharing the same material", () => {
    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshStandardMaterial();
    const fruit = new THREE.InstancedMesh(geometry, material, 2);
    fruit.setMatrixAt(0, new THREE.Matrix4().makeScale(0.9, 0.9, 0.9));
    fruit.setMatrixAt(1, new THREE.Matrix4().makeTranslation(2, 0, 0));
    fruit.setColorAt(0, new THREE.Color().setRGB(0.88, 0.92, 0.96));
    fruit.setColorAt(1, new THREE.Color().setScalar(0.95));
    const original = Array.from(fruit.instanceColor!.array);
    const live = new THREE.Scene();
    live.add(fruit, new THREE.Mesh(geometry, material));
    const photo = buildPhotoScene(live, { width: 4, depth: 5, background: null });
    const baked = photo.scene.children.find((o) => o instanceof THREE.Mesh) as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
    const color = baked.geometry.getAttribute("color");
    const n = geometry.index!.count;
    expect(color.count).toBe(n * 3);
    expect(baked.material.vertexColors).toBe(true);
    for (let i = 0; i < n * 3; i++) {
      const expected = i < n ? [0.88, 0.92, 0.96] : i < n * 2 ? [0.95, 0.95, 0.95] : [1, 1, 1];
      expect(color.getX(i)).toBeCloseTo(expected[0]!, 6);
      expect(color.getY(i)).toBeCloseTo(expected[1]!, 6);
      expect(color.getZ(i)).toBeCloseTo(expected[2]!, 6);
    }
    expect(baked.geometry.getAttribute("position").getX(0)).toBeCloseTo(0.45);
    photo.dispose();
    expect(material.vertexColors).toBe(false);
    expect(geometry.getAttribute("color")).toBeUndefined();
    expect(Array.from(fruit.instanceColor!.array)).toEqual(original);
    fruit.dispose(); geometry.dispose(); material.dispose();
  });

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

  it("bakes combined eyelid and gaze deformations without changing live morph state", () => {
    const geometry = new THREE.PlaneGeometry(1, 1);
    const count = geometry.getAttribute("position").count;
    const deltas = new Float32Array(count * 3);
    const gaze = new Float32Array(count * 3);
    const weights = new Float32Array(count * 4);
    for (let i = 0; i < count; i++) { deltas[i * 3 + 1] = -0.02; gaze[i * 3] = 0.01; weights[i * 4] = 1; }
    geometry.morphAttributes.position = [new THREE.BufferAttribute(deltas, 3), new THREE.BufferAttribute(gaze, 3)];
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
    mesh.morphTargetInfluences![1] = 0.35;
    const live = new THREE.Scene();
    live.add(mesh);
    live.updateMatrixWorld(true);
    mesh.skeleton.update();
    const expected = mesh.getVertexPosition(0, new THREE.Vector3()).applyMatrix4(mesh.matrixWorld);
    const photo = buildPhotoScene(live, { width: 4, depth: 5, background: null });
    const baked = photo.scene.children.find((o) => o instanceof THREE.Mesh) as THREE.Mesh;
    const vertex = new THREE.Vector3().fromBufferAttribute(baked.geometry.getAttribute("position"), 0);
    expect(vertex.distanceTo(expected)).toBeLessThan(1e-6);
    expect(mesh.morphTargetInfluences).toEqual([0.75, 0.35]);
    expect(geometry.getAttribute("position").getY(0)).toBe(0.5);
    photo.dispose();
    geometry.dispose();
    material.dispose();
    mesh.skeleton.dispose();
  });
});
