// @vitest-environment jsdom
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import * as THREE from "three";
import { FullScreenQuad } from "three/examples/jsm/postprocessing/Pass.js";
import type { WebGLPathTracer } from "three-gpu-pathtracer";
import { PhotoMode } from "../PhotoMode";
import { GatedRenderer } from "../GatedRenderer";
import { frameGate } from "../frameGate";
import { usePhotoMode } from "../photoModeStore";

const mocks = vi.hoisted(() => ({
  get: vi.fn(), frame: vi.fn(), hdr: vi.fn(), construct: vi.fn(), scene: vi.fn(),
  workerDispose: vi.fn(), sceneDispose: vi.fn(), denoiseDispose: vi.fn(),
  tracer: {
    setBVHWorker: vi.fn(), setSceneAsync: vi.fn(), setCamera: vi.fn(), updateCamera: vi.fn(),
    renderSample: vi.fn(), dispose: vi.fn(), tiles: { set: vi.fn() }, target: { texture: null }, samples: 0,
    renderToCanvasCallback: undefined as WebGLPathTracer["renderToCanvasCallback"] | undefined,
  },
}));
vi.mock("@react-three/fiber", () => ({
  useThree: (select: (state: { get: typeof mocks.get }) => unknown) => select({ get: mocks.get }),
  useFrame: mocks.frame,
}));
vi.mock("three/examples/jsm/loaders/HDRLoader.js", () => ({
  HDRLoader: class { loadAsync = mocks.hdr; },
}));
vi.mock("three-gpu-pathtracer", async () => {
  const { PerspectiveCamera } = await import("three");
  return {
    WebGLPathTracer: class { constructor() { mocks.construct(); return mocks.tracer; } },
    DenoiseMaterial: class { dispose = mocks.denoiseDispose; },
    PhysicalCamera: class extends PerspectiveCamera { apertureBlades = 0; fStop = 1.4; focusDistance = 25; },
  };
});
vi.mock("three-mesh-bvh/worker", () => ({
  GenerateMeshBVHWorker: class { dispose = mocks.workerDispose; },
}));
vi.mock("../photoScene", () => ({ buildPhotoScene: mocks.scene }));

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  mocks.hdr.mockResolvedValue(null);
  mocks.tracer.setSceneAsync.mockResolvedValue({});
  mocks.tracer.samples = 0;
  mocks.scene.mockReturnValue({ scene: new THREE.Scene(), triangles: 12, dispose: mocks.sceneDispose });
  mocks.get.mockReturnValue({
    scene: new THREE.Scene(), camera: new THREE.PerspectiveCamera(),
    gl: { autoClear: true, getPixelRatio: () => 1, getContextAttributes: () => ({ premultipliedAlpha: true }), getContext: () => ({ getExtension: () => null }), render: vi.fn() },
  });
  frameGate.renderer = null;
  frameGate.photoRenderer = null;
  usePhotoMode.getState().stop();
  usePhotoMode.setState({ denoise: true, dof: false });
});

afterEach(() => {
  cleanup();
  frameGate.renderer = null;
  frameGate.photoRenderer = null;
  usePhotoMode.getState().stop();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

it("keeps tracing across live composer replacement and restores the current renderer", async () => {
  const original = vi.fn(), replacement = vi.fn();
  frameGate.renderer = original;
  usePhotoMode.getState().start();
  const view = render(<><PhotoMode width={4} depth={5} /><GatedRenderer /></>);
  await act(async () => { await vi.advanceTimersByTimeAsync(60); });
  expect(usePhotoMode.getState().status).toBe("tracing");
  const photoRender = frameGate.photoRenderer;
  expect(photoRender).toBeTypeOf("function");

  // A resize or quality switch installs a different live composer while the
  // photo still owns the screen. Exiting must not restore the disposed one.
  frameGate.renderer = replacement;
  const draw = mocks.frame.mock.calls[0]![0] as (state: unknown, delta: number) => void;
  draw(mocks.get(), 1 / 60);
  expect(mocks.tracer.renderSample).toHaveBeenCalledOnce();
  expect(replacement).not.toHaveBeenCalled();
  act(() => {
    usePhotoMode.getState().stop();
    draw(mocks.get(), 1 / 60); // a queued frame before the effect cleans up
    expect(usePhotoMode.getState().status).toBe("off");
  });
  draw(mocks.get(), 1 / 60);
  expect(replacement).toHaveBeenCalledOnce();
  view.unmount();
  expect(frameGate.photoRenderer).toBeNull();
  expect(frameGate.renderer).toBe(replacement);
  expect(mocks.tracer.dispose).toHaveBeenCalledOnce();
  expect(mocks.workerDispose).toHaveBeenCalledOnce();
  expect(mocks.sceneDispose).toHaveBeenCalledOnce();
  expect(mocks.denoiseDispose).toHaveBeenCalledOnce();
});

it("disposes an HDR that finishes after leaving photo mode", async () => {
  let finish!: (texture: THREE.Texture) => void;
  mocks.hdr.mockImplementation(() => new Promise<THREE.Texture>((resolve) => { finish = resolve; }));
  usePhotoMode.getState().start();
  const view = render(<PhotoMode width={4} depth={5} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(60); });
  view.unmount();
  const texture = new THREE.Texture();
  const disposed = vi.spyOn(texture, "dispose");
  await act(async () => { finish(texture); });
  expect(disposed).toHaveBeenCalledOnce();
  expect(mocks.construct).not.toHaveBeenCalled();
  expect(frameGate.photoRenderer).toBeNull();
});

it("closes the GPU frame query even when drawing throws", () => {
  const end = vi.spyOn(frameGate, "end");
  frameGate.renderer = () => { throw new Error("render failed"); };
  render(<GatedRenderer />);
  const draw = mocks.frame.mock.calls[0]![0] as (state: unknown, delta: number) => void;
  expect(() => draw(mocks.get(), 1 / 60)).toThrow("render failed");
  expect(end).toHaveBeenCalledOnce();
});

it("traces a perspective view through a physical lens focused on the frame's centre when depth of field is on", async () => {
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(10, 10), new THREE.MeshStandardMaterial());
  wall.position.set(0, 0, -4);
  wall.updateMatrixWorld(true);
  const photoScene = new THREE.Scene();
  photoScene.add(wall);
  mocks.scene.mockReturnValue({ scene: photoScene, triangles: 2, dispose: mocks.sceneDispose });
  const camera = new THREE.PerspectiveCamera(50, 1.5, 0.1, 100);
  camera.updateMatrixWorld(true);
  mocks.get.mockReturnValue({ ...mocks.get(), camera });
  usePhotoMode.getState().start();
  usePhotoMode.getState().setDof(true, 2.8);
  render(<PhotoMode width={4} depth={5} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(60); });
  act(() => frameGate.photoRenderer!(1 / 60));
  const calls = mocks.tracer.setCamera.mock.calls;
  const lens = calls[calls.length - 1]![0] as THREE.PerspectiveCamera & { fStop: number; focusDistance: number };
  expect(lens).not.toBe(camera);
  expect(lens.fStop).toBe(2.8);
  expect(lens.focusDistance).toBeCloseTo(4, 3);
  expect(usePhotoMode.getState().perspective).toBe(true);
  usePhotoMode.getState().setDof(false);
});

it.each([true, false])("restores the blit shader and renderer after a failed draw with denoise=%s", async (denoise) => {
  usePhotoMode.getState().setDenoise(denoise);
  usePhotoMode.getState().start();
  render(<PhotoMode width={4} depth={5} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(60); });
  mocks.tracer.samples = 1;
  const blit = new THREE.MeshBasicMaterial();
  const quad = new FullScreenQuad(blit);
  vi.spyOn(quad, "render").mockImplementation(() => { throw new Error("blit failed"); });
  const gl = mocks.get().gl;
  const target = new THREE.WebGLRenderTarget(1, 1);
  expect(() => mocks.tracer.renderToCanvasCallback!(target, gl, quad)).toThrow("blit failed");
  expect(gl.autoClear).toBe(true);
  expect(quad.material).toBe(blit);
  target.dispose();
  quad.dispose();
  blit.dispose();
});

it("returns to live rendering and releases photo resources when a frame fails", async () => {
  const live = vi.fn();
  frameGate.renderer = live;
  usePhotoMode.getState().start();
  render(<><PhotoMode width={4} depth={5} /><GatedRenderer /></>);
  await act(async () => { await vi.advanceTimersByTimeAsync(60); });
  const queued = frameGate.photoRenderer!;
  mocks.tracer.renderSample.mockImplementationOnce(() => { throw new Error("photo draw failed"); });
  act(() => { expect(() => queued(1 / 60)).not.toThrow(); });
  expect(usePhotoMode.getState().status).toBe("error");
  expect(usePhotoMode.getState().error).toBe("photo draw failed");
  expect(frameGate.photoRenderer).toBeNull();
  expect(mocks.tracer.dispose).toHaveBeenCalledOnce();
  expect(mocks.denoiseDispose).toHaveBeenCalledOnce();
  expect(mocks.sceneDispose).toHaveBeenCalledOnce();
  expect(mocks.workerDispose).toHaveBeenCalledOnce();
  queued(1 / 60);
  expect(mocks.tracer.renderSample).toHaveBeenCalledOnce();
  const draw = mocks.frame.mock.calls[0]![0] as (state: unknown, delta: number) => void;
  draw(mocks.get(), 1 / 60);
  expect(live).toHaveBeenCalledOnce();
});

it("turns photo mode off when the 3D view unmounts", async () => {
  usePhotoMode.getState().start();
  const view = render(<PhotoMode width={4} depth={5} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(60); });
  expect(usePhotoMode.getState().status).toBe("tracing");
  view.unmount();
  expect(usePhotoMode.getState().status).toBe("off");
  expect(frameGate.photoRenderer).toBeNull();
  expect(mocks.tracer.dispose).toHaveBeenCalledOnce();
});
