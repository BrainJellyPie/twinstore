// The crew in a crew run's playback: each staff member on duty stands at their till, at the shelf they are refilling
// (saying what), or beside the tills waiting for work — a ring on the floor tells them from shoppers.

import { useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";

import type { CustomerResult, Rack, TimelineEvent } from "@/shared/types/domain";
import { useI18n } from "@/shared/i18n/i18n";
import { useSimulationMetricsStore } from "@/stores/simulationMetricsStore";
import { livePlaybackClock } from "../realistic/playbackClock";
import { crewAt, crewIndex, type CrewDoing, type CrewPlan } from "../utils/crewAt";
import { crewSpot, shopperSides } from "../utils/crewSpot";
import { AssetPersona } from "./AssetPersona";

const STAFF_COLOR = "#0d9488";

function said(description: string): TimelineEvent {
  return { elapsed_sec: 0, x: 0, y: 0, action: "browse", duration: 0, target_rack: "", face: null, description,
    product_sku: "", product_name: "", price: 0 };
}

function signature(doing: CrewDoing[]): string {
  return doing.map((d) => d.kind === "refill" ? `${d.member}:r:${d.rackId}:${d.face}:${d.name}`
    : d.kind === "till" ? `${d.member}:t:${d.rackId}` : `${d.member}:i`).join("|");
}

export function CrewLayer({ racks, customers, plan }: { racks: Rack[]; customers: CustomerResult[]; plan: CrewPlan }) {
  const { t } = useI18n();
  const tills = useMemo(() => racks.filter((r) => r.type === "counter"), [racks]);
  const byId = useMemo(() => new Map(racks.map((r) => [r.id, r])), [racks]);
  const sides = useMemo(() => shopperSides(tills, customers), [tills, customers]);
  const index = useMemo(() => crewIndex(plan.tasks), [plan.tasks]);
  const [doing, setDoing] = useState<CrewDoing[]>([]);
  const last = useRef("");

  useFrame(() => {
    // The loop's exact clock when it runs; the published minute otherwise.
    const clock = livePlaybackClock.current;
    const metrics = useSimulationMetricsStore.getState();
    const now = crewAt(index, plan, clock ? clock.day.current : metrics.currentDay,
      clock ? clock.time.current : metrics.currentMinute);
    const key = signature(now);
    if (key !== last.current) {
      last.current = key;
      setDoing(now);
    }
  });

  return (
    <>
      {doing.map((d) => {
        const spot = crewSpot(d, byId, tills, sides);
        if (!spot) return null;
        return (
          <group key={`crew-${d.member}`} name="crew-member" position={[spot.x, 0, spot.z]}>
            <AssetPersona personaId={`crew-${d.member}`} facing={spot.facing} isMoving={false} color={STAFF_COLOR}
              label={t("crewLabel", { n: d.member + 1 })} highlighted
              event={d.kind === "refill" ? said(t("crewRefilling", { name: d.name })) : null} />
          </group>
        );
      })}
    </>
  );
}
