import { expect, it, vi } from "vitest";
import * as THREE from "three";
import type * as PathTracingTypes from "three-gpu-pathtracer";
// Test the ESM entry used by Vite, rather than the package's legacy Node bundle.
import * as BrowserPathTracing from "three-gpu-pathtracer/src/index.js";

// The package exports this material but omits the deprecated API from its declarations.
const PathTracing = BrowserPathTracing as typeof PathTracingTypes & {
  PhysicalPathTracingMaterial: new () => THREE.ShaderMaterial;
};

interface Disposable { dispose(): void }
interface PackedTexture extends THREE.Texture {
  renderTarget: THREE.WebGLArrayRenderTarget & { fsQuad: { material: THREE.ShaderMaterial } };
}

it("releases packed arrays and owned uniforms without disposing borrowed maps", () => {
  const material = new PathTracing.PhysicalPathTracingMaterial();
  const owned: Disposable[] = [material];
  for (const name of ["bvh", "attributesArray", "materialIndexAttribute", "materials", "envMapInfo",
    "stratifiedTexture", "stratifiedOffsetTexture"]) {
    owned.push(material.uniforms[name]!.value as Disposable);
  }
  for (const name of ["textures", "iesProfiles"]) {
    const texture = material.uniforms[name]!.value as PackedTexture;
    expect(texture.renderTarget.texture).toBe(texture);
    owned.push(texture.renderTarget, texture.renderTarget.fsQuad.material);
  }
  owned.push((material.uniforms.lights!.value as { tex: THREE.Texture }).tex);
  const background = new THREE.Texture(), sobol = new THREE.Texture();
  material.uniforms.backgroundMap!.value = background;
  material.uniforms.sobolTexture!.value = sobol;
  const disposed = owned.map((value) => vi.spyOn(value, "dispose"));
  const borrowed = [background, sobol].map((value) => vi.spyOn(value, "dispose"));
  material.dispose();
  disposed.forEach((spy) => expect(spy).toHaveBeenCalledOnce());
  borrowed.forEach((spy) => expect(spy).not.toHaveBeenCalled());
  background.dispose(); sobol.dispose();
});

it.each([true, false])("releases both trace renderers with shared material = %s", (shared) => {
  const primary = new THREE.ShaderMaterial();
  const secondary = shared ? primary : new THREE.ShaderMaterial();
  const tracer = {
    _quad: { dispose: vi.fn(), material: new THREE.ShaderMaterial() },
    _pathTracer: { material: primary, dispose: vi.fn() },
    _lowResPathTracer: { material: secondary, dispose: vi.fn() },
    _generator: { geometry: new THREE.BufferGeometry() },
    _internalBackground: new THREE.Texture(),
    _colorBackground: new THREE.Texture(),
  };
  const resources = new Set<Disposable>([primary, secondary, tracer._quad.material,
    tracer._generator.geometry, tracer._internalBackground, tracer._colorBackground]);
  const disposed = [...resources].map((resource) => vi.spyOn(resource, "dispose"));
  PathTracing.WebGLPathTracer.prototype.dispose.call(tracer as unknown as PathTracingTypes.WebGLPathTracer);
  disposed.forEach((spy) => expect(spy).toHaveBeenCalledOnce());
  expect(tracer._quad.dispose).toHaveBeenCalledOnce();
  expect(tracer._pathTracer.dispose).toHaveBeenCalledOnce();
  expect(tracer._lowResPathTracer.dispose).toHaveBeenCalledOnce();
});

it.each([true, false])("respects rasterizeScene = %s while the low-resolution shader compiles", (enabled) => {
  const rasterize = vi.fn();
  const tracer = {
    _pathTracer: { material: { backgroundAlpha: 1 } },
    _lowResPathTracer: {},
    _renderer: { extensions: { get: () => ({}) } },
    _clock: { getDelta: () => 0.016, getElapsedTime: () => 0.2 },
    _quad: { material: { opacity: 0 } },
    _updateScale: vi.fn(),
    samples: 0, minSamples: 1, renderDelay: 100, isCompiling: true,
    enablePathTracing: true, renderToCanvas: true, dynamicLowRes: true,
    rasterizeScene: enabled, rasterizeSceneCallback: rasterize,
  };
  PathTracing.WebGLPathTracer.prototype.renderSample.call(tracer as unknown as PathTracingTypes.WebGLPathTracer);
  expect(rasterize).toHaveBeenCalledTimes(enabled ? 1 : 0);
});
