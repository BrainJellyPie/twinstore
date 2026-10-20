// Per-rack KPI overlay: a glowing floor pad under each rack (brightness ∝ revenue
// share) and a compact label with revenue, buyers and — when shoppers also stopped
// without buying — the stop→buy conversion.

import { useMemo } from "react";
import { Html } from "@react-three/drei";

import type { Rack } from "@/shared/types/domain";
import type { RackStats } from "@/shared/api/client";
import { rackBounds, rackWorldCenter } from "@/shared/utils/grid";
import { formatMoney, formatPercent } from "@/shared/utils/money";

interface Props {
  racks: Rack[];
  stats: RackStats[];
  currency: string;
}

const LOW = [148, 163, 184]; // slate-400
const HIGH = [16, 185, 129]; // emerald-500

export function RackPerformanceLayer({ racks, stats, currency }: Props) {
  const byId = useMemo(() => new Map(stats.map((s) => [s.rack_id, s])), [stats]);
  const maxRevenue = Math.max(1, ...stats.map((s) => s.revenue));

  return (
    <>
      {racks.map((rack) => {
        const s = byId.get(rack.id);
        if (!s) return null;
        const t = s.revenue / maxRevenue;
        const color = `rgb(${LOW.map((l, i) => Math.round(l + (HIGH[i]! - l) * t)).join(",")})`;
        const [cx, , cz] = rackWorldCenter(rack);
        const { w, d } = rackBounds(rack);
        const stopToBuy = s.visitors ? s.buyers / s.visitors : 0;
        return (
          <group key={rack.id} position={[cx, 0, cz]}>
            <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
              <planeGeometry args={[w + 0.5, d + 0.5]} />
              <meshBasicMaterial color={color} transparent opacity={0.25 + 0.55 * t} depthWrite={false} />
            </mesh>
            <Html position={[0, 1.55, 0]} center zIndexRange={[5, 0]} style={{ pointerEvents: "none" }}>
              <div className="whitespace-nowrap rounded-md border bg-background/90 px-1.5 py-0.5 text-[10px] leading-tight shadow-sm">
                <div className="font-medium">{rack.rack_name || rack.id}</div>
                <div className="tabular-nums text-muted-foreground">
                  {formatMoney(s.revenue, currency, { compact: true })} · {s.buyers.toLocaleString()} buyers
                  {s.visitors > s.buyers && ` · ${formatPercent(stopToBuy, 0)} stop→buy`}
                </div>
              </div>
            </Html>
          </group>
        );
      })}
    </>
  );
}
