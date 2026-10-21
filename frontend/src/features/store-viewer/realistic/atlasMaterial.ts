// MeshStandardMaterial that reads its map (and emissive map) from one cell of a
// texture atlas chosen per instance via the `aCell` instanced attribute.

import * as THREE from "three";

export interface AtlasMaterialOptions {
  roughness?: number;
  metalness?: number;
  side?: THREE.Side;
  // Fraction of the albedo added as emission (printed labels stay legible in
  // shadow) — no second texture fetch.
  selfLight?: number;
  // Lambert instead of PBR: far cheaper per pixel for thousands of tiny
  // packages under software GL; no environment reflections.
  cheap?: boolean;
}

export function createAtlasMaterial(
  texture: THREE.Texture,
  cellScale: [number, number],
  opts: AtlasMaterialOptions = {},
): THREE.MeshStandardMaterial | THREE.MeshLambertMaterial {
  const mat = opts.cheap
    ? new THREE.MeshLambertMaterial({ map: texture, side: opts.side ?? THREE.FrontSide })
    : new THREE.MeshStandardMaterial({
        map: texture,
        roughness: opts.roughness ?? 0.5,
        metalness: opts.metalness ?? 0,
        side: opts.side ?? THREE.FrontSide,
      });
  const scale = new THREE.Vector2(cellScale[0], cellScale[1]);
  const self = { value: opts.selfLight ?? 0.1 };
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uCellScale = { value: scale };
    shader.uniforms.uSelfLight = self;
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform float uSelfLight;")
      .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\ntotalEmissiveRadiance += diffuseColor.rgb * uSelfLight;");
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nattribute vec2 aCell;\nuniform vec2 uCellScale;")
      .replace(
        "#include <uv_vertex>",
        [
          "#include <uv_vertex>",
          "#ifdef USE_MAP",
          "  vMapUv = aCell + vMapUv * uCellScale;",
          "#endif",
        ].join("\n"),
      );
  };
  mat.customProgramCacheKey = () => "parastore-atlas-v2";
  // Photo mode bakes the cell offset into UVs (the path tracer has no vertex shader hook).
  mat.userData.atlasCellScale = scale;
  return mat;
}

export function canvasTexture(canvas: HTMLCanvasElement, opts: { anisotropy?: number; repeat?: boolean } = {}): THREE.CanvasTexture {
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = opts.anisotropy ?? 4;
  if (opts.repeat) {
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
  }
  tex.needsUpdate = true;
  return tex;
}
