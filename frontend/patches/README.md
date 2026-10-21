# Path tracer resource ownership

`three-gpu-pathtracer@0.0.24.patch` fixes GPU resources retained after leaving Photo
mode in the ESM browser entry used by Vite. pnpm applies it on install through
`pnpm-workspace.yaml`.

The upstream `WebGLPathTracer.dispose()` leaves the low-resolution renderer,
packed texture render targets, material uniforms, and generated geometry alive.
The patch releases those resources, including the unused low-resolution material
replaced on the first preview frame. Shared trace materials are disposed once;
borrowed scene backgrounds and renderer-owned Sobol maps keep their owners.
The temporary Sobol shader is also released after generating its texture.

The patch respects `rasterizeScene: false` while a low-resolution shader compiles.
Previously this path rendered the temporary scene anyway, leaving a Three.js
transmission target for its glass after every photo. Photo mode retains the live
frame until the path-traced preview is ready.

Three.js r183 replaces the texture in `WebGLArrayRenderTarget` without preserving
its `renderTarget` reference. The patch restores that reference in
`RenderTarget2DArray` so disposing packed uniforms can free their framebuffers.

Resource ownership is covered by `pathTracerResources.test.ts`. Browser validation
opens Photo mode, waits for a sample, closes it, and repeats while comparing
`renderer.info.memory` after live rendering settles. Recheck both when upgrading
the library; remove this patch once upstream provides equivalent cleanup.

Upstream: https://github.com/gkjohnson/three-gpu-pathtracer (MIT).
