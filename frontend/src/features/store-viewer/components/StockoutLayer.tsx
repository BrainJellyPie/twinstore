// Shelves standing empty at the playback clock, in a shared-store run: a red mark on the floor and a label naming
// the products that are gone, so a stock-out shows where and when it happens.

import { useMemo } from "react";
import { Html } from "@react-three/drei";

import type { EmptySpell } from "@/shared/api/client";
import { emptyAt } from "../utils/emptyShelves";
import type { Rack } from "@/shared/types/domain";
import { useI18n } from "@/shared/i18n/i18n";
import { rackBounds, rackWorldCenter } from "@/shared/utils/grid";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";

const NAMES_SHOWN = 2;

export function StockoutLayer({ racks, spells }: { racks: Rack[]; spells: EmptySpell[] }) {
  const { t } = useI18n();
  const day = useSimulationMetricsStore((s) => s.currentDay);
  const minute = useSimulationMetricsStore((s) => s.currentMinute);
  const gone = useMemo(() => emptyAt(spells, day, minute), [spells, day, minute]);
  const byId = useMemo(() => new Map(racks.map((r) => [r.id, r])), [racks]);

  return (
    <>
      {[...gone.entries()].map(([rackId, names]) => {
        const rack = byId.get(rackId);
        if (!rack) return null;
        const [cx, , cz] = rackWorldCenter(rack);
        const { w, d } = rackBounds(rack);
        const shown = names.slice(0, NAMES_SHOWN).join(", ");
        const more = names.length - NAMES_SHOWN;
        return (
          <group key={rackId} position={[cx, 0, cz]}>
            <mesh position={[0, 0.035, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <planeGeometry args={[w + 0.4, d + 0.4]} />
              <meshBasicMaterial color="#ef4444" transparent opacity={0.35} depthWrite={false} />
            </mesh>
            <Html position={[0, 1.9, 0]} center zIndexRange={[6, 0]} style={{ pointerEvents: "none" }}>
              <div className="whitespace-nowrap rounded-md border border-destructive/50 bg-background/90 px-1.5 py-0.5 text-[0.72rem] leading-tight text-destructive shadow-sm">
                {more > 0 ? t("opsSoldOutMore", { names: shown, count: more }) : t("opsSoldOut", { names: shown })}
              </div>
            </Html>
          </group>
        );
      })}
    </>
  );
}
