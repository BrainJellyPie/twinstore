import * as THREE from "three";
import { Pass } from "three/examples/jsm/postprocessing/Pass.js";

// MeshNormalMaterial's stock shader omits alpha testing. Keep its skinning,
// morph and instancing support, and add the same mask sampling as the visible mesh.
class MaskedNormalMaterial extends THREE.MeshNormalMaterial {
  map: THREE.Texture | null = null;
  alphaMap: THREE.Texture | null = null;

  constructor() {
    super({ blending: THREE.NoBlending });
    this.onBeforeCompile = (shader) => {
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <uv_pars_fragment>", `#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>`)
        .replace("#include <clipping_planes_fragment>", `#include <clipping_planes_fragment>
#include <map_fragment>
#include <alphamap_fragment>
#include <alphatest_fragment>`);
    };
  }
}

// GTAO accepts an external GBuffer. A per-material normal pass preserves hair
// and leaf cutouts, while glass and translucent decals do not become occluders.
export class StoreGBufferPass extends Pass {
  readonly target: THREE.WebGLRenderTarget;
  private readonly materials = new Map<THREE.Material, MaskedNormalMaterial>();

  constructor(private readonly scene: THREE.Scene, private readonly camera: THREE.Camera, width: number, height: number) {
    super();
    this.needsSwap = false;
    const depth = new THREE.DepthTexture(width, height, THREE.UnsignedInt248Type);
    depth.format = THREE.DepthStencilFormat;
    this.target = new THREE.WebGLRenderTarget(width, height, {
      minFilter: THREE.NearestFilter,
      magFilter: THREE.NearestFilter,
      type: THREE.HalfFloatType,
      depthTexture: depth,
    });
  }

  setSize(width: number, height: number) {
    this.target.setSize(Math.max(1, width), Math.max(1, height));
  }

  private normalFor(source: THREE.Material): MaskedNormalMaterial {
    let normal = this.materials.get(source);
    if (!normal) {
      normal = new MaskedNormalMaterial();
      this.materials.set(source, normal);
    }
    const mapped = source as THREE.Material & { map?: THREE.Texture | null; alphaMap?: THREE.Texture | null; flatShading?: boolean };
    const map = source.alphaTest > 0 ? mapped.map ?? null : null;
    const alphaMap = source.alphaTest > 0 ? mapped.alphaMap ?? null : null;
    const flat = mapped.flatShading ?? false;
    if (normal.map !== map || normal.alphaMap !== alphaMap || normal.side !== source.side || normal.flatShading !== flat) normal.needsUpdate = true;
    normal.map = map;
    normal.alphaMap = alphaMap;
    normal.side = source.side;
    normal.flatShading = flat;
    normal.alphaTest = source.alphaTest;
    normal.opacity = source.opacity;
    normal.visible = source.visible && source.opacity > 0 && (!source.transparent || source.alphaTest > 0);
    return normal;
  }

  render(renderer: THREE.WebGLRenderer) {
    const previous = {
      target: renderer.getRenderTarget(),
      face: renderer.getActiveCubeFace(),
      mip: renderer.getActiveMipmapLevel(),
      clearColor: renderer.getClearColor(new THREE.Color()),
      clearAlpha: renderer.getClearAlpha(),
      autoClear: renderer.autoClear,
      shadowAuto: renderer.shadowMap.autoUpdate,
      shadowUpdate: renderer.shadowMap.needsUpdate,
      override: this.scene.overrideMaterial,
      background: this.scene.background,
    };
    const replaced: { mesh: THREE.Mesh; material: THREE.Material | THREE.Material[] }[] = [];
    const hidden: THREE.Object3D[] = [];
    const used = new Set<THREE.Material>();
    const replace = (source: THREE.Material) => { used.add(source); return this.normalFor(source); };
    try {
      this.scene.traverseVisible((object) => {
        if (object instanceof THREE.Line || object instanceof THREE.Points || object instanceof THREE.Sprite || ("isLine2" in object && object.isLine2) || ("isLineSegments2" in object && object.isLineSegments2)) {
          hidden.push(object);
          object.visible = false;
        } else if (object instanceof THREE.Mesh) {
          replaced.push({ mesh: object, material: object.material });
          object.material = Array.isArray(object.material) ? object.material.map(replace) : replace(object.material);
        }
      });
      this.scene.overrideMaterial = null;
      this.scene.background = null;
      renderer.shadowMap.autoUpdate = renderer.shadowMap.needsUpdate = false;
      renderer.autoClear = false;
      renderer.setRenderTarget(this.target);
      renderer.setClearColor(0x7777ff, 1);
      renderer.clear();
      renderer.render(this.scene, this.camera);
    } finally {
      for (const { mesh, material } of replaced) mesh.material = material;
      for (const object of hidden) object.visible = true;
      this.scene.overrideMaterial = previous.override;
      this.scene.background = previous.background;
      renderer.shadowMap.autoUpdate = previous.shadowAuto;
      renderer.shadowMap.needsUpdate = previous.shadowUpdate;
      renderer.autoClear = previous.autoClear;
      renderer.setClearColor(previous.clearColor, previous.clearAlpha);
      renderer.setRenderTarget(previous.target, previous.face, previous.mip);
      // Source materials can disappear when shoppers or fixtures are removed.
      for (const [source, normal] of this.materials) {
        if (!used.has(source)) { normal.dispose(); this.materials.delete(source); }
      }
    }
  }

  dispose() {
    this.materials.forEach((material) => material.dispose());
    this.materials.clear();
    this.target.dispose();
  }
}
