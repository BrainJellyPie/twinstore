// Top-down map of the neighborhood: roads, buildings (tinted by use, opacity by population),
// venues, our store with its 50 % / 80 % catchment rings, and the strongest origin flows.
// Wheel to zoom, drag to pan; in "place" mode a click opens a venue at that spot.

import { useEffect, useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";

import type { Town, TownDemand, TownVenue } from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";

import { BUILDING_COLORS, labelOf, ROAD_WIDTH, VENUE_COLORS, VENUE_LABELS } from "./townStyle";

export type MapMode = "inspect" | "place" | "remove";

export function TownMap({
  town,
  demand,
  mode,
  onPlace,
  onRemove,
  highlightVenueId,
}: {
  town: Town;
  demand?: TownDemand;
  mode: MapMode;
  onPlace: (x: number, y: number) => void;
  onRemove: (venue: TownVenue) => void;
  highlightVenueId?: string | null;
}) {
  const { t, locale } = useI18n();
  const S = town.size_m;
  const [view, setView] = useState({ x: 0, y: 0, w: S });
  const drag = useRef<{ px: number; py: number; vx: number; vy: number; moved: boolean } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    // React's passive wheel listener cannot keep the surrounding workspace still.
    const preventScroll = (event: globalThis.WheelEvent) => {
      if (event.deltaY !== 0) event.preventDefault();
    };
    svg.addEventListener("wheel", preventScroll, { passive: false });
    return () => svg.removeEventListener("wheel", preventScroll);
  }, []);
  const focal = town.venues.find((v) => v.is_focal);
  // World (y north) → SVG (y down).
  const fy = (y: number) => S - y;

  const maxPop = useMemo(
    () => Math.max(1, ...town.buildings.map((b) => b.residents + b.workers + b.students + b.daily_passersby / 20)),
    [town.buildings],
  );
  const flows = useMemo(() => {
    if (!demand || !focal) return [];
    const byId = new Map(town.buildings.map((b) => [b.id, b]));
    return [...demand.origin_shares]
      .sort((a, b) => b.share - a.share)
      .slice(0, 30)
      .map((o) => ({ o, b: byId.get(o.building_id) }))
      .filter((x): x is { o: (typeof demand.origin_shares)[number]; b: NonNullable<ReturnType<typeof byId.get>> } => !!x.b);
  }, [demand, focal, town.buildings]);
  const maxShare = flows.length ? Math.max(...flows.map((f) => f.o.share)) : 1;

  const toWorld = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return null;
    const point = svg.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    const position = point.matrixTransform(matrix.inverse());
    return { x: position.x, y: S - position.y };
  };

  const onWheel = (e: WheelEvent<SVGSVGElement>) => {
    if (e.deltaY === 0) return;
    const p = toWorld(e.clientX, e.clientY);
    if (!p) return;
    const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
    const w = Math.min(S * 1.2, Math.max(S / 12, view.w * factor));
    const sx = p.x, sy = S - p.y;
    setView({ x: sx - ((sx - view.x) * w) / view.w, y: sy - ((sy - view.y) * w) / view.w, w });
  };
  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    drag.current = { px: e.clientX, py: e.clientY, vx: view.x, vy: view.y, moved: false };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM()?.inverse();
    if (!d || !matrix) return;
    const dx = (e.clientX - d.px) * matrix.a + (e.clientY - d.py) * matrix.c;
    const dy = (e.clientX - d.px) * matrix.b + (e.clientY - d.py) * matrix.d;
    if (Math.abs(e.clientX - d.px) + Math.abs(e.clientY - d.py) > 4) d.moved = true;
    setView((v) => ({ ...v, x: d.vx - dx, y: d.vy - dy }));
  };
  const onUp = (e: PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    drag.current = null;
    if (d && !d.moved && mode === "place") {
      const p = toWorld(e.clientX, e.clientY);
      if (p) onPlace(Math.round(p.x), Math.round(p.y));
    }
  };

  return (
    <svg
      ref={svgRef}
      viewBox={`${view.x} ${view.y} ${view.w} ${view.w}`}
      className={`h-full w-full touch-none select-none rounded-2xl bg-[var(--map-ground)] ${mode === "place" ? "cursor-crosshair" : "cursor-grab"}`}
      onWheel={onWheel}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      role="img"
      aria-label={t("areaMapOf", { name: town.name })}
    >
      {/* Roads */}
      {town.roads.map((r) => (
        <polyline
          key={r.id}
          points={r.points.map(([x, y]) => `${x},${fy(y)}`).join(" ")}
          fill="none"
          stroke={r.kind === "arterial" ? "var(--map-road)" : "var(--map-road-minor)"}
          strokeWidth={ROAD_WIDTH[r.kind] ?? 6}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}

      {/* Buildings */}
      {town.buildings.map((b) => {
        const pop = b.residents + b.workers + b.students + b.daily_passersby / 20;
        return (
          <rect
            key={b.id}
            x={b.x - b.width / 2}
            y={fy(b.y) - b.depth / 2}
            width={b.width}
            height={b.depth}
            rx={1.5}
            fill={BUILDING_COLORS[b.kind] ?? "#d4d4d8"}
            style={{ fillOpacity: `calc(var(--map-building-alpha) * ${(b.kind === "park" ? 0.7 : 0.35 + 0.6 * Math.min(1, pop / maxPop)).toFixed(3)})` }}
            stroke="var(--map-building-stroke)"
            strokeOpacity={0.35}
            strokeWidth={0.8}
          >
            <title>
              {t("areaBuildingFloors", { name: b.name || b.kind, floors: b.floors }) +
                (b.residents ? t("areaBuildingResidents", { count: b.residents }) : "") +
                (b.workers ? t("areaBuildingWorkers", { count: b.workers }) : "") +
                (b.students ? t("areaBuildingStudents", { count: b.students }) : "") +
                (b.daily_passersby ? t("areaBuildingPassengers", { count: b.daily_passersby.toLocaleString(locale) }) : "")}
            </title>
          </rect>
        );
      })}

      {/* Catchment rings */}
      {focal && demand && (
        <>
          <circle cx={focal.x} cy={fy(focal.y)} r={demand.catchment_radius_80_m / 1.3} fill="none" stroke="var(--map-focal)" strokeDasharray="10 8" strokeWidth={2} opacity={0.5} />
          <circle cx={focal.x} cy={fy(focal.y)} r={demand.catchment_radius_50_m / 1.3} fill="var(--map-focal)" fillOpacity={0.08} stroke="var(--map-focal)" strokeWidth={2} opacity={0.8} />
        </>
      )}

      {/* Origin flows */}
      {focal &&
        flows.map(({ o, b }) => (
          <line
            key={o.building_id + o.segment}
            x1={b.x}
            y1={fy(b.y)}
            x2={focal.x}
            y2={fy(focal.y)}
            stroke="var(--map-focal)"
            strokeOpacity={0.15 + 0.5 * (o.share / maxShare)}
            strokeWidth={1 + 7 * (o.share / maxShare)}
            strokeLinecap="round"
          />
        ))}

      {/* Venues */}
      {town.venues.map((v) => {
        const hl = v.id === highlightVenueId;
        return (
          <g
            key={v.id}
            transform={`translate(${v.x},${fy(v.y)})`}
            onPointerUp={(e) => {
              if (mode === "remove" && !v.is_focal) {
                // The map's own pointer-up never runs: end its drag here, or the next plain move pans the map.
                drag.current = null;
                e.stopPropagation();
                onRemove(v);
              }
            }}
            className={mode === "remove" && !v.is_focal ? "cursor-pointer" : undefined}
          >
            {v.is_focal ? (
              <>
                <circle r={17} fill="var(--map-focal)" stroke="var(--map-ground)" strokeWidth={4} />
                <path d="M-8 3 L0 -8 L8 3 Z M-6 3 h12 v6 h-12 Z" fill="white" />
              </>
            ) : (
              <circle
                r={hl ? 11 : 7.5}
                fill={VENUE_COLORS[v.category] ?? "#334155"}
                stroke={hl ? "var(--foreground)" : "var(--map-ground)"}
                strokeWidth={hl ? 3 : 2}
              />
            )}
            <title>{t("areaVenueTitle", { name: v.name, category: labelOf(VENUE_LABELS, v.category, t) }) + (v.is_focal ? t("areaVenueOurs") : "")}</title>
          </g>
        );
      })}
    </svg>
  );
}
