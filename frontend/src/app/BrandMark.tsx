// The TwinStore mark: a solid shelf block (the store) and its glowing wireframe double (the
// digital twin) inside a slowly turning aurora ring — the same drawing as the app icon.

import { useId } from "react";

import { cn } from "@/shared/utils/cn";

export function BrandMark({ className }: { className?: string }) {
  const twin = useId();
  return (
    <span
      className={cn(
        "relative grid size-9 shrink-0 place-items-center overflow-hidden rounded-[0.8rem] bg-[#0b0c10] shadow-[inset_0_1px_0_rgb(255_255_255/0.18),0_10px_26px_-12px_var(--heat-2)]",
        className,
      )}
      aria-hidden
    >
      <span className="absolute -inset-3 animate-spin-slow bg-[conic-gradient(from_0deg,var(--heat-1),var(--heat-2),var(--heat-3),var(--volt),var(--heat-1))] blur-[5px]" />
      <span className="absolute inset-[2px] rounded-[0.68rem] bg-[#0b0c10]/85" />
      <svg viewBox="3.5 3 17.5 17" className="relative size-[74%]">
        <defs>
          <linearGradient id={twin} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#3fdfff" />
            <stop offset="0.55" stopColor="#a586ff" />
            <stop offset="1" stopColor="#ff5fc6" />
          </linearGradient>
        </defs>
        <g fill="none" stroke={`url(#${twin})`} strokeWidth="1.3" strokeLinejoin="round">
          <path d="M15.2 4.4 19.7 7v5.2l-4.5 2.6-4.5-2.6V7Z" />
          <path d="M10.7 7 15.2 9.6 19.7 7M15.2 9.6v5.2" />
        </g>
        <path d="M9 8 13.5 10.6 9 13.2 4.5 10.6Z" fill="#f2f4f8" />
        <path d="M4.5 10.6 9 13.2v5.2l-4.5-2.6Z" fill="#b4bacb" />
        <path d="M13.5 10.6 9 13.2v5.2l4.5-2.6Z" fill="#6b7186" />
        <path d="M9 8 13.5 10.6v5.2L9 18.4l-4.5-2.6v-5.2Z" fill="none" stroke="white" strokeWidth="0.9" strokeLinejoin="round" />
        <circle cx="15.2" cy="4.4" r="1.3" fill="var(--volt)" />
      </svg>
    </span>
  );
}
