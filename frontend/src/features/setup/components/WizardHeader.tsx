import { Check } from "lucide-react";

import { cn } from "@/shared/utils/cn";

interface WizardHeaderProps {
  title: string;
  steps: ReadonlyArray<{ index: number; label: string; hint?: string }>;
  activeIndex: number;
}

// The wizard is a real sequence: a vertical stepper whose finished steps are checked and whose
// active step glows.
export function WizardHeader({ title, steps, activeIndex }: WizardHeaderProps) {
  return (
    <div className="space-y-8">
      <div>
        <div className="eyebrow">Create</div>
        <h1 className="mt-2 font-display text-[clamp(2.4rem,4vw,3.4rem)] leading-[0.95] tracking-[-0.05em]">
          {title}
          <span className="block font-accent text-[0.9em] tracking-[-0.01em]"><span className="aurora-text pr-1">in two steps.</span></span>
        </h1>
      </div>
      <ol className="relative space-y-1">
        {steps.map((s, i) => {
          const active = s.index === activeIndex;
          const done = s.index < activeIndex;
          return (
            <li key={s.index} className="relative flex gap-4 pb-6" aria-current={active ? "step" : undefined}>
              {i < steps.length - 1 && (
                <span className={cn("absolute top-10 bottom-0 left-[1.15rem] w-px", done ? "aurora-gradient" : "bg-foreground/12")} aria-hidden />
              )}
              <span
                className={cn(
                  "num relative grid size-[2.3rem] shrink-0 place-items-center rounded-full border text-sm font-semibold transition-colors",
                  active && "border-transparent bg-primary text-primary-foreground shadow-[0_0_0_6px_color-mix(in_oklab,var(--primary)_16%,transparent)]",
                  done && "border-transparent bg-foreground text-background",
                  !active && !done && "text-muted-foreground",
                )}
              >
                {done ? <Check className="size-4" /> : s.index}
              </span>
              <div className="pt-1.5">
                <div className={cn("text-[1.05rem] font-semibold tracking-[-0.02em]", !active && !done && "text-muted-foreground")}>{s.label}</div>
                {s.hint && <p className="mt-1 max-w-xs text-sm leading-relaxed text-muted-foreground">{s.hint}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
