import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Html, useGLTF, useAnimations } from "@react-three/drei";
import * as THREE from "three";
import type { Rack } from "@/shared/types/domain";
import { rackWorldCenter } from "@/shared/utils/grid";
import { marketAssetFor, ALL_MARKET_ASSETS } from "@/shared/utils/assetMap";
import { useGlbModel } from "@/shared/hooks/useGlbModel";
import { uniformScaleToTile } from "@/shared/utils/glbHelpers";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { DiningTable } from "./DiningTable";

const GHOST_URL = "/assets/ghost/character-ghost.glb";
const GHOST_HEIGHT = 0.55;

ALL_MARKET_ASSETS.forEach((url) => useGLTF.preload(url));
useGLTF.preload(GHOST_URL);

interface AssetInstanceProps {
  url: string;
  cellCenter: [number, number, number];
  overrideMap?: THREE.Texture | null;
  hovered?: boolean;
  disableRaycast?: boolean;
}

function AssetInstance({ url, cellCenter, overrideMap, hovered = false, disableRaycast = false }: AssetInstanceProps) {
  const { clone, bbox, offset } = useGlbModel(url, { overrideMap });
  const scale = uniformScaleToTile(bbox);

  // useGlbModel's clone shares material refs across instances of the same GLB URL.
  // Mutating emissive directly causes cross-contamination — every rack of the same
  // type lights up. So on mount, clone the material per instance and dispose on
  // unmount/clone swap. This is a side effect, so it lives in useLayoutEffect
  // (not useMemo) to avoid leaks under React Strict Mode double-invocation.
  type OwnMaterial = { mat: THREE.MeshStandardMaterial; baseEmissive: THREE.Color; baseIntensity: number };
  const [ownMaterials, setOwnMaterials] = useState<OwnMaterial[]>([]);

  useLayoutEffect(() => {
    const list: OwnMaterial[] = [];
    clone.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      // Disable raycast only for multi-mesh GLBs like shelf (where shelves + items
      // are split across many meshes); AssetFixture's invisible hitbox catches the
      // raycast instead. Single-body GLBs (fridge/counter) keep raycast on so hits
      // follow the actual fixture shape.
      if (disableRaycast) mesh.raycast = () => null;
      const mat = mesh.material;
      if (Array.isArray(mat)) {
        const cloned: THREE.Material[] = mat.map((src) => src.clone());
        mesh.material = cloned;
        for (const c of cloned) {
          if (c instanceof THREE.MeshStandardMaterial) {
            list.push({ mat: c, baseEmissive: c.emissive.clone(), baseIntensity: c.emissiveIntensity });
          }
        }
      } else if (mat) {
        const cloned = mat.clone();
        mesh.material = cloned;
        if (cloned instanceof THREE.MeshStandardMaterial) {
          list.push({ mat: cloned, baseEmissive: cloned.emissive.clone(), baseIntensity: cloned.emissiveIntensity });
        }
      }
    });
    setOwnMaterials(list);
    return () => {
      for (const entry of list) entry.mat.dispose();
    };
  }, [clone, disableRaycast]);

  useEffect(() => {
    for (const entry of ownMaterials) {
      if (hovered) {
        entry.mat.emissive.setHex(0xffffff);
        entry.mat.emissiveIntensity = 0.25;
      } else {
        entry.mat.emissive.copy(entry.baseEmissive);
        entry.mat.emissiveIntensity = entry.baseIntensity;
      }
    }
  }, [ownMaterials, hovered]);

  return (
    <group position={cellCenter} scale={scale}>
      <primitive object={clone} position={offset} />
    </group>
  );
}

export function CounterGhost() {
  const { clone, bbox, offset, animations } = useGlbModel(GHOST_URL, { skinned: true });
  const rawH = bbox.size.y > 0.001 ? bbox.size.y : 1;
  const scale = GHOST_HEIGHT / rawH;

  const { actions } = useAnimations(animations, clone);
  const paidCount = useSimulationMetricsStore((s) => s.paidCount);
  const prevPaidRef = useRef(paidCount);
  const [animName, setAnimName] = useState("static");

  useEffect(() => {
    if (paidCount > prevPaidRef.current) {
      setAnimName("emote-yes");
      const timer = setTimeout(() => setAnimName("static"), 2000);
      prevPaidRef.current = paidCount;
      return () => clearTimeout(timer);
    }
    prevPaidRef.current = paidCount;
  }, [paidCount]);

  useEffect(() => {
    const action = actions[animName];
    if (!action) return;
    action.reset().fadeIn(0.15).play();
    return () => { action.fadeOut(0.15); };
  }, [animName, actions]);

  return (
    <group position={[0, 0, -0.45]} scale={scale}>
      <primitive object={clone} position={offset} />
    </group>
  );
}

interface AssetFixtureProps {
  rack: Rack;
  variationTexture?: THREE.Texture | null;
}

export function AssetFixture({ rack, variationTexture }: AssetFixtureProps) {
  const url = marketAssetFor(rack);
  const center = rackWorldCenter(rack);

  const shapeRows = rack.shape.length;
  const shapeCols = rack.shape[0]?.length ?? 0;

  const cells = useMemo(() => {
    const list: { col: number; row: number }[] = [];
    for (let row = 0; row < shapeRows; row++) {
      const arr = rack.shape[row];
      if (!arr) continue;
      for (let col = 0; col < arr.length; col++) {
        if (arr[col]) list.push({ col, row });
      }
    }
    return list;
  }, [rack.shape, shapeRows]);

  const setHoveredRackId = useSimulationStore((s) => s.setHoveredRackId);
  const setSelectedRackId = useSimulationStore((s) => s.setSelectedRackId);
  const hoveredRackId = useSimulationStore((s) => s.hoveredRackId);
  const isHovered = hoveredRackId === rack.id;

  if (!url && rack.type !== "table") return null;

  // GLB authoring convention is mirrored vs. the grid-editor face convention along
  // the N-S axis, so flip the rotation sign for every fixture. Effect: 0/180
  // unchanged, 90 ↔ 270 swapped. Visible on assets with left/right asymmetry
  // (counter, fridge, shelf-end); symmetric assets look identical either way.
  const groupRot = (-(rack.rotation ?? 0) * Math.PI) / 180;

  // entrance/exit are not display racks — no hover/click.
  const interactive = rack.type !== "entrance" && rack.type !== "exit";
  // Only shelf is split into multiple sub-meshes, which flickers on hover — delegate
  // raycast to a single invisible hitbox. Other types are single-body, so the GLB
  // itself acts as the hitbox.
  const useHitbox = rack.type === "shelf";

  return (
    <group
      position={center}
      rotation={[0, groupRot, 0]}
      // Use onPointerEnter/Leave — fires once per group entry/exit.
      // onPointerOver/Out fires per mesh inside the group, which flickers on multi-mesh
      // GLBs (e.g. shelf) when the cursor moves through inter-mesh gaps.
      onPointerEnter={
        interactive
          ? (e) => {
              e.stopPropagation();
              setHoveredRackId(rack.id);
            }
          : undefined
      }
      onPointerLeave={
        interactive
          ? (e) => {
              e.stopPropagation();
              if (useSimulationStore.getState().hoveredRackId === rack.id) {
                setHoveredRackId(null);
              }
            }
          : undefined
      }
      onClick={
        interactive
          ? (e) => {
              e.stopPropagation();
              setSelectedRackId(rack.id);
            }
          : undefined
      }
    >
      {rack.type === "table" ? <DiningTable width={shapeCols} depth={shapeRows} hovered={isHovered} /> : cells.map(({ col, row }) => {
        const cx = col - shapeCols / 2 + 0.5;
        const cz = row - shapeRows / 2 + 0.5;
        return (
          <AssetInstance
            key={`${col}-${row}`}
            url={url!}
            cellCenter={[cx, 0, cz]}
            overrideMap={variationTexture}
            hovered={isHovered}
            disableRaycast={useHitbox}
          />
        );
      })}
      {rack.type === "counter" && rack.design_variant === "b" && <CounterGhost />}
      {/* shelf-only invisible hitbox — removes hover flicker when the cursor moves
          between sub-meshes of a multi-mesh GLB. Height is fixed to 1 to match the
          shelf's actual height so empty space above isn't part of the hover area. */}
      {interactive && useHitbox && (
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[shapeCols, 1, shapeRows]} />
          <meshBasicMaterial visible={false} />
        </mesh>
      )}
      {interactive && isHovered && rack.rack_name && (
        <Html
          position={[0, 1.4, 0]}
          center
          style={{ pointerEvents: "none" }}
        >
          <div className="rounded-md border bg-background/95 px-2 py-1 text-xs font-medium shadow-sm whitespace-nowrap">
            {rack.rack_name}
          </div>
        </Html>
      )}
    </group>
  );
}
