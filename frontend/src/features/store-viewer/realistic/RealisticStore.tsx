import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { INTERIOR_DESIGNS } from "./designThemes";
import type { Rack, StoreDesign } from "@/shared/types/domain";
import { CEILING_HEIGHT, M, QUALITY_PRESETS, type GraphicsQuality } from "./constants";
import { buildStore } from "./buildStore";
import { createShellMaterials, disposeMaterials, NO_CAST, NO_RECEIVE } from "./materials";
import { layoutProducts } from "./productLayout";
import { buildProductMeshes } from "./productMeshes";
import { canvasTexture } from "./atlasMaterial";
import { createCeilingCanvas, createFloorCanvases } from "./canvasArt";
import { useFontsReady } from "./useFontsReady";
import { AutoDoors } from "./AutoDoors";
import { RackHitboxes } from "./RackHitboxes";
import { acquireRoomEnvironment } from "./envCache";
import { ReflectiveFloor } from "./ReflectiveFloor";
import { useRealisticSettings } from "./graphicsSettings";
import { useScannedMaterial } from "./useScannedMaterial";
import { usePottedPlants } from "./usePottedPlants";

interface Props {
  width: number;
  depth: number;
  racks: Rack[];
  currency: string;
  quality: GraphicsQuality;
  designTheme?: StoreDesign;
}

const noRaycast = () => undefined;

function Surfaces({ width, depth, quality, designTheme }: { width: number; depth: number; quality: GraphicsQuality; designTheme: StoreDesign }) {
  const palette = INTERIOR_DESIGNS[designTheme];
  const high = quality === "high";
  // Poly Haven's scan covers 1.5 metres, independently of the store grid size.
  const scanned = useScannedMaterial("floor_tiles_08", width / (1.5 * M), depth / (1.5 * M), quality);
  const res = useMemo(() => {
    const { color, rough } = createFloorCanvases(4, 1024);
    const floorMap = canvasTexture(color, { anisotropy: high ? 8 : 2, repeat: true });
    floorMap.repeat.set(width / 4, depth / 4);
    const roughMap = canvasTexture(rough, { anisotropy: high ? 8 : 1, repeat: true });
    roughMap.colorSpace = THREE.NoColorSpace;
    roughMap.repeat.set(width / 4, depth / 4);
    const ceilMap = canvasTexture(createCeilingCanvas(), { repeat: true });
    ceilMap.repeat.set(width / 2, depth / 2);
    const ceiling = new THREE.MeshStandardMaterial({ map: ceilMap, color: palette.ceiling, roughness: 0.95 });
    return { floorMap, roughMap, ceilMap, ceiling };
  }, [width, depth, high, palette.ceiling]);

  useEffect(
    () => () => {
      res.floorMap.dispose();
      res.roughMap.dispose();
      res.ceilMap.dispose();
      res.ceiling.dispose();
    },
    [res],
  );

  return (
    <>
      <ReflectiveFloor
        width={width}
        depth={depth}
        map={scanned?.map ?? res.floorMap}
        roughnessMap={scanned?.roughnessMap ?? res.roughMap}
        normalMap={scanned?.normalMap ?? null}
        reflections={high}
        color={palette.floor}
      />
      <mesh
        name="realistic-ceiling"
        position={[width / 2, CEILING_HEIGHT, depth / 2]}
        rotation={[Math.PI / 2, 0, 0]}
        material={res.ceiling}
        raycast={noRaycast}
      >
        <planeGeometry args={[width, depth]} />
      </mesh>
    </>
  );
}

export function RealisticStore({ width, depth, racks, currency, quality, designTheme = "classic" }: Props) {
  const preset = QUALITY_PRESETS[quality];
  const fontsReady = useFontsReady();

  const built = useMemo(() => buildStore(width, depth, racks, quality === "high"), [width, depth, racks, quality]);
  const plants = usePottedPlants(quality === "high" && built.doors.length > 0, built.doors);
  const signTexture = useMemo(() => {
    const t = new THREE.CanvasTexture(built.signAtlas.canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 2;
    return t;
  }, [built]);
  // "medium": only small metal/glass parts sample the environment (see RealisticLighting).
  const get = useThree((s) => s.get);
  const partEnv = useMemo(() => (quality === "high" ? null : acquireRoomEnvironment(get().gl)), [quality, get]);
  const woodMaps = useScannedMaterial("wood_table_001", 1, 1, quality);
  // The plaster is authored at one repeat/metre; Medium avoids these extra maps.
  const wallMaps = useScannedMaterial(quality === "high" ? "plaster_001" : null, 1 / M, 1 / M, quality);
  // Author the fine metal finish at a half-metre repeat, independent of beam dimensions.
  const metalMaps = useScannedMaterial(quality === "high" ? "metal_032" : null, 2 / M, 2 / M, quality);
  // Poly Haven's paving scan covers 2.12 m. Stores without an exterior door have no pavement.
  const pavementMaps = useScannedMaterial(quality === "high" && built.storefront ? "pavement_02" : null, 1 / (2.12 * M), 1 / (2.12 * M), quality);
  const materials = useMemo(() => createShellMaterials(quality, signTexture, partEnv, woodMaps, wallMaps, designTheme, metalMaps, pavementMaps), [quality, signTexture, partEnv, woodMaps, wallMaps, designTheme, metalMaps, pavementMaps]);
  const layout = useMemo(() => layoutProducts(built.plans, { maxRows: preset.maxRows }), [built, preset.maxRows]);
  const products = useMemo(
    () => buildProductMeshes(layout, currency, quality === "high" ? 160 : 128, quality === "high", quality === "high" ? 4 : 1, quality !== "high"),
    [layout, currency, quality],
  );

  useEffect(() => {
    if (!fontsReady) return;
    built.signAtlas.redraw();
    signTexture.needsUpdate = true;
    products.atlases.forEach((a) => a.redraw());
    products.textures.forEach((t) => {
      t.needsUpdate = true;
    });
  }, [fontsReady, built, signTexture, products]);

  useEffect(
    () => () => {
      for (const g of built.geometries.values()) g.dispose();
      for (const g of built.upperGeometries.values()) g.dispose();
      signTexture.dispose();
    },
    [built, signTexture],
  );
  useEffect(() => () => disposeMaterials(materials), [materials]);
  useEffect(() => products.loadAssets(() => { get().gl.shadowMap.needsUpdate = true; }), [products, get]);
  useEffect(() => () => products.dispose(), [products]);

  // Compile every program off the main thread (KHR_parallel_shader_compile)
  // while the store stays hidden; a synchronous first draw would freeze the page
  // for seconds under software GL. Readiness is reported once it has drawn.
  const groupRef = useRef<THREE.Group>(null);
  const framesRef = useRef(0);
  useLayoutEffect(() => {
    const g = groupRef.current;
    if (!g) return;
    let alive = true;
    framesRef.current = 0;
    useRealisticSettings.getState().setRealisticReady(false);
    const { gl, scene, camera } = get();
    let pending: Promise<unknown> = Promise.resolve();
    // Without KHR_parallel_shader_compile (e.g. SwiftShader) there is nothing
    // to gain: programs compile on first draw.
    if (gl.extensions.has("KHR_parallel_shader_compile")) {
      g.visible = true;
      try {
        pending = gl.compileAsync(g, camera, scene);
      } catch {
        // Fall back to compiling on first draw.
      }
      g.visible = false;
    }
    pending
      .catch(() => undefined)
      .then(() => {
        if (alive) {
          g.visible = true;
          gl.shadowMap.needsUpdate = true;
        }
      });
    return () => {
      alive = false;
      g.visible = true;
      useRealisticSettings.getState().setRealisticReady(false);
    };
  }, [get, built, materials, products, plants]);

  // Fine package geometry only when the shelves are big on screen.
  const fineRef = useRef<boolean | null>(null);
  const upperRef = useRef<THREE.Group>(null);
  useFrame(({ camera }) => {
    // Camera-side walls close up only in the first-person view.
    if (upperRef.current) upperRef.current.visible = !(camera as THREE.OrthographicCamera).isOrthographicCamera;
    if (groupRef.current?.visible && framesRef.current < 2 && ++framesRef.current === 2) {
      useRealisticSettings.getState().setRealisticReady(true);
    }
    const ortho = (camera as THREE.OrthographicCamera).isOrthographicCamera;
    const fine = !ortho || (camera as THREE.OrthographicCamera).zoom > 190;
    if (fineRef.current !== fine) {
      fineRef.current = fine;
      products.setDetail(fine);
    }
  });
  useEffect(() => {
    fineRef.current = null;
  }, [products]);

  const meshes = [...built.geometries.entries()];
  const upperMeshes = [...built.upperGeometries.entries()];

  return (
    <group ref={groupRef}>
      <Surfaces width={width} depth={depth} quality={quality} designTheme={designTheme} />
      {meshes.map(([key, geom]) => (
        <mesh
          key={key}
          name={`shell-${key}`}
          geometry={geom}
          material={materials[key]}
          visible={!plants || (key !== "plant" && key !== "pot")}
          castShadow={!NO_CAST.has(key)}
          receiveShadow={!NO_RECEIVE.has(key)}
          renderOrder={key === "ao" ? 1 : key === "glass" || key === "lidGlass" ? 3 : 0}
          raycast={noRaycast}
        />
      ))}
      <group ref={upperRef} visible={false}>
        {upperMeshes.map(([key, geom]) => (
          <mesh
            key={key}
            name={`upper-${key}`}
            geometry={geom}
            material={materials[key]}
            castShadow={!NO_CAST.has(key)}
            receiveShadow={!NO_RECEIVE.has(key)}
            renderOrder={key === "glass" ? 3 : 0}
            raycast={noRaycast}
          />
        ))}
      </group>
      <primitive object={products.group} />
      {plants && <primitive object={plants} dispose={null} />}
      <AutoDoors doors={built.doors} materials={materials} />
      <RackHitboxes plans={built.plans} />
    </group>
  );
}
