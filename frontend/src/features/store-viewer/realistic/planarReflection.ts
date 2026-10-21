// Planar floor reflection that works with both the orthographic isometric
// camera and the perspective shopper camera (three's Reflector assumes a
// perspective projection for its oblique clip plane). Nothing in the store sits
// below y = 0 except the slab, which is hidden during the mirror pass, so no
// clip plane is needed.

import * as THREE from "three";
import { CEILING_HEIGHT } from "./constants";

export interface PlanarReflection {
  update: (gl: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.Camera, floor: THREE.Object3D | null) => void;
  dispose: () => void;
}

// Meshes that must not appear in the mirror image (below-floor slab etc.).
const HIDE_IN_MIRROR = new Set(["shell-plinth", "shell-pavement", "shell-curb", "realistic-floor", "shell-ao", "scene-ground"]);
const CEILING = new Set(["realistic-ceiling", "shell-ceilingLight"]);

export function attachPlanarReflection(material: THREE.MeshStandardMaterial, strength = 0.9): PlanarReflection {
  const target = new THREE.WebGLRenderTarget(512, 512, { type: THREE.HalfFloatType, samples: 0 });
  target.texture.colorSpace = THREE.LinearSRGBColorSpace;
  const textureMatrix = new THREE.Matrix4();
  const uniforms = {
    tReflect: { value: target.texture },
    uTextureMatrix: { value: textureMatrix },
    uReflectStrength: { value: strength },
    uTexel: { value: new THREE.Vector2(1 / 512, 1 / 512) },
  };

  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nuniform mat4 uTextureMatrix;\nvarying vec4 vReflectCoord;")
      .replace(
        "#include <project_vertex>",
        "#include <project_vertex>\nvReflectCoord = uTextureMatrix * modelMatrix * vec4( transformed, 1.0 );",
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        "#include <common>\nuniform sampler2D tReflect;\nuniform float uReflectStrength;\nuniform vec2 uTexel;\nvarying vec4 vReflectCoord;",
      )
      .replace(
        "#include <opaque_fragment>",
        [
          "{",
          "  vec2 ruv = vReflectCoord.xy / vReflectCoord.w;",
          "  vec2 blur = uTexel * ( 0.75 + roughnessFactor * roughnessFactor * 10.0 );",
          "  vec4 rc = texture2D( tReflect, ruv ) * 0.25;",
          "  rc += texture2D( tReflect, ruv + vec2( blur.x, 0.0 ) ) * 0.125;",
          "  rc += texture2D( tReflect, ruv - vec2( blur.x, 0.0 ) ) * 0.125;",
          "  rc += texture2D( tReflect, ruv + vec2( 0.0, blur.y ) ) * 0.125;",
          "  rc += texture2D( tReflect, ruv - vec2( 0.0, blur.y ) ) * 0.125;",
          "  rc += texture2D( tReflect, ruv + blur ) * 0.0625;",
          "  rc += texture2D( tReflect, ruv - blur ) * 0.0625;",
          "  rc += texture2D( tReflect, ruv + vec2( blur.x, -blur.y ) ) * 0.0625;",
          "  rc += texture2D( tReflect, ruv + vec2( -blur.x, blur.y ) ) * 0.0625;",
          // Dielectric Fresnel: quiet at normal incidence, stronger along the aisle.
          // Blend reflected coverage instead of adding light over every floor pixel.
          "  float ndv = saturate( dot( normal, geometryViewDir ) );",
          "  float fresnel = 0.04 + 0.96 * pow( 1.0 - ndv, 5.0 );",
          "  float weight = saturate( uReflectStrength * fresnel * ( 1.0 - roughnessFactor ) * rc.a );",
          "  outgoingLight = mix( outgoingLight, rc.rgb / max( rc.a, 0.0001 ), weight );",
          "}",
          "#include <opaque_fragment>",
        ].join("\n"),
      );
  };
  material.customProgramCacheKey = () => "parastore-floor-reflect-v2";
  material.needsUpdate = true;

  let mirrorCam: THREE.Camera | null = null;
  const camPos = new THREE.Vector3();
  const rot = new THREE.Matrix4();
  const look = new THREE.Vector3();
  const normal = new THREE.Vector3(0, 1, 0);
  const size = new THREE.Vector2();
  const hidden: THREE.Object3D[] = [];
  const clearColor = new THREE.Color();

  const update: PlanarReflection["update"] = (gl, scene, camera, floor) => {
    if (!floor) return;
    camera.updateMatrixWorld();
    camPos.setFromMatrixPosition(camera.matrixWorld);
    if (camPos.y <= 0.01 && !(camera as THREE.OrthographicCamera).isOrthographicCamera) return;

    gl.getDrawingBufferSize(size);
    const w = Math.max(64, Math.round(size.x * 0.5));
    const h = Math.max(64, Math.round(size.y * 0.5));
    if (target.width !== w || target.height !== h) {
      target.setSize(w, h);
      uniforms.uTexel.value.set(1 / w, 1 / h);
    }

    const ortho = (camera as THREE.OrthographicCamera).isOrthographicCamera;
    if (!mirrorCam || (mirrorCam as THREE.OrthographicCamera).isOrthographicCamera !== ortho) {
      mirrorCam = ortho ? new THREE.OrthographicCamera() : new THREE.PerspectiveCamera();
    }
    const mc = mirrorCam as THREE.PerspectiveCamera | THREE.OrthographicCamera;
    // Reflect position, view direction and up across y = 0.
    rot.extractRotation(camera.matrixWorld);
    look.set(0, 0, -1).applyMatrix4(rot).add(camPos);
    mc.position.set(camPos.x, -camPos.y, camPos.z);
    mc.up.set(0, 1, 0).applyMatrix4(rot).reflect(normal);
    mc.lookAt(look.x, -look.y, look.z);
    mc.updateMatrixWorld();
    mc.projectionMatrix.copy((camera as THREE.PerspectiveCamera).projectionMatrix);
    mc.projectionMatrixInverse.copy((camera as THREE.PerspectiveCamera).projectionMatrixInverse);

    textureMatrix.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
    textureMatrix.multiply(mc.projectionMatrix);
    textureMatrix.multiply(mc.matrixWorldInverse);

    const hideCeiling = camPos.y > CEILING_HEIGHT || ortho;
    hidden.length = 0;
    scene.traverse((o) => {
      if (!o.visible) return;
      if (HIDE_IN_MIRROR.has(o.name) || (hideCeiling && CEILING.has(o.name)) || o.userData.hideInMirror) {
        o.visible = false;
        hidden.push(o);
      }
    });

    // Transparent clear so only reflected geometry adds to the floor.
    const prevBackground = scene.background;
    const prevFog = scene.fog;
    scene.background = null;
    scene.fog = null;
    const prevTarget = gl.getRenderTarget();
    const prevShadowAuto = gl.shadowMap.autoUpdate;
    const prevXr = gl.xr.enabled;
    gl.getClearColor(clearColor);
    const prevAlpha = gl.getClearAlpha();
    try {
      gl.xr.enabled = false;
      gl.shadowMap.autoUpdate = false;
      gl.setClearColor(0x000000, 0);
      gl.setRenderTarget(target);
      gl.clear();
      gl.render(scene, mc);
    } finally {
      gl.setRenderTarget(prevTarget);
      gl.setClearColor(clearColor, prevAlpha);
      gl.shadowMap.autoUpdate = prevShadowAuto;
      gl.xr.enabled = prevXr;
      scene.background = prevBackground;
      scene.fog = prevFog;
      for (const o of hidden) o.visible = true;
    }
  };

  return {
    update,
    dispose: () => target.dispose(),
  };
}
