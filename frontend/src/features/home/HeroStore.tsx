// The home hero: an isometric convenience store with shoppers walking its aisles and leaving
// foot-traffic heat behind them — what Parastore simulates, shown instead of told.

import { useEffect, useState } from "react";

const TILE_W = 30;
const TILE_H = 15;
const iso = (x: number, y: number, z = 0) => [(x - y) * TILE_W, (x + y) * TILE_H - z] as const;
const pts = (list: (readonly [number, number])[]) => list.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(" ");

function Box({ x, y, w = 1, d = 1, h, top, left, right }: { x: number; y: number; w?: number; d?: number; h: number; top: string; left: string; right: string }) {
  const p = (dx: number, dy: number, z: number) => iso(x + dx, y + dy, z);
  return (
    <g>
      <polygon points={pts([p(0, d, 0), p(w, d, 0), p(w, d, h), p(0, d, h)])} fill={left} />
      <polygon points={pts([p(w, 0, 0), p(w, d, 0), p(w, d, h), p(w, 0, h)])} fill={right} />
      <polygon points={pts([p(0, 0, h), p(w, 0, h), p(w, d, h), p(0, d, h)])} fill={top} />
    </g>
  );
}

// Walkways through the store (tile coordinates, path centers).
const ROUTES: [number, number][][] = [
  [[0.5, 6.5], [1.5, 6.5], [1.5, 1.5], [7.5, 1.5], [7.5, 4.5], [3.5, 4.5], [3.5, 6.5], [0.5, 6.5]],
  [[0.5, 6.5], [6.5, 6.5], [6.5, 4.5], [8.5, 4.5], [8.5, 1.5], [4.5, 1.5], [4.5, 4.5], [2.5, 4.5], [2.5, 6.5], [0.5, 6.5]],
  [[0.5, 6.5], [1.5, 6.5], [1.5, 4.5], [5.5, 4.5], [5.5, 1.5], [2.5, 1.5], [2.5, 4.5], [1.5, 4.5], [1.5, 6.5], [0.5, 6.5]],
];
const SHOPPER_COLORS = ["var(--heat-1)", "var(--heat-2)", "var(--heat-3)"];

export function HeroStore() {
  const [animate, setAnimate] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const sync = () => setAnimate(!mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const paths = ROUTES.map((r) => "M" + r.map(([x, y]) => iso(x, y, 0).map((v) => v.toFixed(1)).join(",")).join(" L"));
  const floor = [iso(0, 0), iso(10, 0), iso(10, 7), iso(0, 7)];
  const shelf = { top: "var(--hero-shelf-top)", left: "var(--hero-shelf-left)", right: "var(--hero-shelf-right)" };
  const fridge = { top: "var(--hero-fridge-top)", left: "var(--hero-fridge-left)", right: "var(--hero-fridge-right)" };

  return (
    <svg viewBox="-230 -60 560 330" className="hero-store h-full w-full" role="img" aria-label="Shoppers walking through a store">
      <defs>
        <filter id="heat-blur" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      {/* Floor and back walls */}
      <polygon points={pts(floor)} fill="var(--hero-floor)" stroke="var(--hero-line)" strokeWidth={1} />
      {Array.from({ length: 11 }, (_, i) => (
        <line key={`gx${i}`} x1={iso(i, 0)[0]} y1={iso(i, 0)[1]} x2={iso(i, 7)[0]} y2={iso(i, 7)[1]} stroke="var(--hero-line)" strokeWidth={0.6} />
      ))}
      {Array.from({ length: 8 }, (_, i) => (
        <line key={`gy${i}`} x1={iso(0, i)[0]} y1={iso(0, i)[1]} x2={iso(10, i)[0]} y2={iso(10, i)[1]} stroke="var(--hero-line)" strokeWidth={0.6} />
      ))}
      <polygon points={pts([iso(0, 0), iso(10, 0), iso(10, 0, 70), iso(0, 0, 70)])} fill="var(--hero-wall)" />
      <polygon points={pts([iso(0, 0), iso(0, 7), iso(0, 7, 70), iso(0, 0, 70)])} fill="var(--hero-wall-side)" />

      {/* Foot-traffic heat along the walkways */}
      <g filter="url(#heat-blur)" opacity={0.55}>
        {paths.map((d, i) => (
          <path key={i} d={d} fill="none" stroke={SHOPPER_COLORS[i]} strokeWidth={16} strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </g>

      {/* Fridges along the back wall, glowing */}
      {Array.from({ length: 8 }, (_, i) => (
        <g key={`f${i}`}>
          <Box x={1 + i} y={0} h={56} {...fridge} />
          <polygon points={pts([iso(1.12 + i, 1, 8), iso(1.88 + i, 1, 8), iso(1.88 + i, 1, 50), iso(1.12 + i, 1, 50)])} fill="var(--hero-fridge-glow)" />
        </g>
      ))}
      {/* Gondola islands */}
      {[2, 3, 4, 5, 6, 7].map((x) => <Box key={`a${x}`} x={x} y={2.6} h={30} d={0.8} {...shelf} />)}
      {[3, 4, 5, 6, 7].map((x) => <Box key={`b${x}`} x={x} y={5.2} h={30} d={0.8} {...shelf} />)}
      {/* Price-tag rails */}
      {[2, 3, 4, 5, 6, 7].map((x) => (
        <polygon key={`t${x}`} points={pts([iso(x, 3.4, 14), iso(x + 1, 3.4, 14), iso(x + 1, 3.4, 10), iso(x, 3.4, 10)])} fill="var(--tag)" />
      ))}
      {/* Counter at the entrance */}
      <Box x={0.1} y={5.1} w={0.8} d={1.3} h={26} top="var(--hero-counter-top)" left="var(--hero-counter-left)" right="var(--hero-counter-right)" />

      {/* Shoppers */}
      {paths.map((d, i) => (
        <g key={`s${i}`}>
          {[0, 1].map((k) => (
            <g key={k}>
              <ellipse rx={7} ry={3.5} fill="black" opacity={0.18}>
                {animate && <animateMotion dur={`${14 + i * 3}s`} begin={`${-k * 6 - i * 2}s`} repeatCount="indefinite" path={d} />}
              </ellipse>
              <g>
                <rect x={-4.5} y={-22} width={9} height={14} rx={4} fill={SHOPPER_COLORS[(i + k) % 3]} />
                <circle cy={-26} r={4.5} fill="var(--hero-skin)" />
                {animate && <animateMotion dur={`${14 + i * 3}s`} begin={`${-k * 6 - i * 2}s`} repeatCount="indefinite" path={d} />}
              </g>
            </g>
          ))}
        </g>
      ))}
    </svg>
  );
}
