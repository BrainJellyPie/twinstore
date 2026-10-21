// The Parastore mark: an isometric shelf block inside a slowly turning aurora ring.

import { cn } from "@/shared/utils/cn";

export function BrandMark({ className }: { className?: string }) {
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
      <svg viewBox="0 0 24 24" className="relative size-[58%]">
        <path d="M12 3.5 19.5 7.8v8.4L12 20.5 4.5 16.2V7.8Z" fill="none" stroke="white" strokeWidth="1.7" strokeLinejoin="round" />
        <path d="M4.5 7.8 12 12.1l7.5-4.3M12 12.1v8.4" fill="none" stroke="white" strokeWidth="1.7" strokeLinejoin="round" opacity="0.7" />
        <circle cx="19.2" cy="19.2" r="2.6" fill="var(--volt)" />
      </svg>
    </span>
  );
}
