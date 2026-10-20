import { cn } from "@/shared/utils/cn";

interface WizardHeaderProps {
  title: string;
  steps: ReadonlyArray<{ index: number; label: string }>;
  activeIndex: number;
}

// The wizard is a real sequence, so its steps are numbered; the active and finished steps light up
// the heat ramp.
export function WizardHeader({ title, steps, activeIndex }: WizardHeaderProps) {
  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl leading-tight font-bold tracking-tight">{title}</h1>
      <ol className="grid gap-3" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
        {steps.map((s) => {
          const active = s.index === activeIndex;
          const done = s.index < activeIndex;
          return (
            <li key={s.index} className="space-y-2" aria-current={active ? "step" : undefined}>
              <div className={cn("h-1.5 rounded-full", active || done ? "heat-gradient" : "bg-muted")} />
              <div className={cn("flex items-baseline gap-2 text-base", active ? "font-semibold text-foreground" : "text-muted-foreground")}>
                <span className={cn("font-display tabular-nums", active ? "text-primary" : "")}>{s.index}</span>
                {s.label}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
