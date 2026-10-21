import { expect, it, vi } from "vitest";
import * as THREE from "three";
import { StoreGBufferPass } from "../StoreGBufferPass";

function renderer(render: () => void) {
  let target: THREE.WebGLRenderTarget | null = null;
  const color = new THREE.Color(0x123456);
  let alpha = 0.4;
  return {
    autoClear: true,
    shadowMap: { autoUpdate: true, needsUpdate: true },
    getRenderTarget: () => target,
    getActiveCubeFace: () => 2,
    getActiveMipmapLevel: () => 1,
    setRenderTarget: vi.fn((value: THREE.WebGLRenderTarget | null) => { target = value; }),
    getClearColor: (out: THREE.Color) => out.copy(color),
    getClearAlpha: () => alpha,
    setClearColor: (value: THREE.ColorRepresentation, a: number) => { color.set(value); alpha = a; },
    clear: vi.fn(), render,
  };
}

it.each([false, true])("preserves cutout masks and restores live state after the normal pass (throws: %s)", (throws) => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera();
  const background = new THREE.Color("white"), override = new THREE.MeshBasicMaterial();
  scene.background = background; scene.overrideMaterial = override;
  const map = new THREE.Texture(), alphaMap = new THREE.Texture();
  const hair = new THREE.MeshStandardMaterial({ map, alphaMap, alphaTest: 0.1, side: THREE.DoubleSide });
  const glass = new THREE.MeshStandardMaterial({ transparent: true, opacity: 0.14 });
  const original = [hair, glass];
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(), original);
  const line = Object.assign(new THREE.Mesh(), { isLine2: true });
  const hidden = new THREE.Mesh(); hidden.visible = false;
  scene.add(mesh, line, hidden);
  const pass = new StoreGBufferPass(scene, camera, 16, 16);
  const gl = renderer(() => {
    const materials: THREE.Material[] = mesh.material;
    expect(materials[0]).toMatchObject({ map, alphaMap, alphaTest: 0.1, side: THREE.DoubleSide, visible: true });
    expect(materials[1]!.visible).toBe(false);
    expect(scene.overrideMaterial).toBeNull();
    expect(scene.background).toBeNull();
    expect(line.visible).toBe(false);
    expect(gl.shadowMap).toEqual({ autoUpdate: false, needsUpdate: false });
    if (throws) throw new Error("interrupted");
  });
  const run = () => pass.render(gl as unknown as THREE.WebGLRenderer);
  if (throws) expect(run).toThrow("interrupted"); else run();
  expect(mesh.material).toBe(original);
  expect(line.visible).toBe(true); expect(hidden.visible).toBe(false);
  expect(scene.background).toBe(background); expect(scene.overrideMaterial).toBe(override);
  expect(gl.autoClear).toBe(true);
  expect(gl.shadowMap).toEqual({ autoUpdate: true, needsUpdate: true });
  expect(gl.getClearAlpha()).toBe(0.4);
  expect(gl.getClearColor(new THREE.Color()).getHex()).toBe(0x123456);
  expect(gl.setRenderTarget).toHaveBeenLastCalledWith(null, 2, 1);
  pass.dispose();
});

it("reuses normal materials, updates masks, and releases removed materials without disposing borrowed textures", () => {
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera();
  const source = new THREE.MeshStandardMaterial({ alphaTest: 0.1, map: new THREE.Texture() });
  const first = new THREE.Mesh(new THREE.PlaneGeometry(), source), second = first.clone();
  scene.add(first, second);
  const pass = new StoreGBufferPass(scene, camera, 16, 16);
  let normal: THREE.Material | undefined;
  const gl = renderer(() => {
    if (scene.children.length) {
      normal ??= first.material;
      expect(first.material).toBe(normal);
      expect(second.material).toBe(normal);
      expect(normal).toMatchObject({ map: source.map, side: source.side });
    }
  });
  pass.render(gl as unknown as THREE.WebGLRenderer);
  const disposeNormal = vi.spyOn(normal!, "dispose");
  const oldMap = source.map!, disposeOldMap = vi.spyOn(oldMap, "dispose");
  source.map = new THREE.Texture(); source.side = THREE.DoubleSide;
  const disposeMap = vi.spyOn(source.map, "dispose");
  pass.render(gl as unknown as THREE.WebGLRenderer);
  expect(disposeNormal).not.toHaveBeenCalled();
  scene.clear(); pass.render(gl as unknown as THREE.WebGLRenderer);
  expect(disposeNormal).toHaveBeenCalledOnce();
  pass.dispose();
  expect(disposeNormal).toHaveBeenCalledOnce();
  expect(disposeOldMap).not.toHaveBeenCalled(); expect(disposeMap).not.toHaveBeenCalled();
});
