import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { attachPlanarReflection } from "../planarReflection";

describe("floor reflection render state", () => {
  it.each([false, true])("restores the viewer after the mirror pass (render throws: %s)", (throws) => {
    const scene = new THREE.Scene();
    const background = new THREE.Color("#223344");
    const fog = new THREE.Fog("#223344", 10, 50);
    scene.background = background;
    scene.fog = fog;
    const floor = new THREE.Object3D();
    floor.name = "realistic-floor";
    const ceiling = new THREE.Object3D();
    ceiling.name = "realistic-ceiling";
    const hidden = new THREE.Object3D();
    hidden.name = "shell-ao";
    hidden.visible = false;
    scene.add(floor, ceiling, hidden);
    const camera = new THREE.OrthographicCamera(-4, 4, 3, -3, 0.1, 100);
    camera.position.set(4, 3, 5);
    camera.lookAt(0, 0, 0);

    const previousTarget = new THREE.WebGLRenderTarget(100, 100);
    let target: THREE.WebGLRenderTarget | null = previousTarget;
    const color = new THREE.Color("#182430");
    const originalColor = color.clone();
    let alpha = 0.7;
    const gl = {
      shadowMap: { autoUpdate: true }, xr: { enabled: true },
      getDrawingBufferSize: (size: THREE.Vector2) => size.set(800, 600),
      getRenderTarget: () => target,
      setRenderTarget: (value: THREE.WebGLRenderTarget | null) => { target = value; },
      getClearColor: (value: THREE.Color) => value.copy(color),
      getClearAlpha: () => alpha,
      setClearColor: (value: THREE.ColorRepresentation, nextAlpha: number) => { color.set(value); alpha = nextAlpha; },
      clear: vi.fn(),
      render: () => {
        expect(alpha).toBe(0);
        expect(scene.background).toBeNull();
        expect(scene.fog).toBeNull();
        expect(floor.visible).toBe(false);
        expect(ceiling.visible).toBe(false);
        if (throws) throw new Error("render interrupted");
      },
    };
    const material = new THREE.MeshStandardMaterial();
    const reflection = attachPlanarReflection(material);
    const update = () => reflection.update(gl as unknown as THREE.WebGLRenderer, scene, camera, floor);
    if (throws) expect(update).toThrow("render interrupted");
    else update();
    expect(target).toBe(previousTarget);
    expect(color.equals(originalColor)).toBe(true);
    expect(alpha).toBe(0.7);
    expect(gl.xr.enabled).toBe(true);
    expect(gl.shadowMap.autoUpdate).toBe(true);
    expect(scene.background).toBe(background);
    expect(scene.fog).toBe(fog);
    expect(floor.visible).toBe(true);
    expect(ceiling.visible).toBe(true);
    expect(hidden.visible).toBe(false);
    reflection.dispose();
    material.dispose();
    previousTarget.dispose();
  });
});
