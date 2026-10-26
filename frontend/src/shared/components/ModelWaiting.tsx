// A model request in progress: what is happening and, once it takes a while, that a small local model can take
// minutes (or another `hint` for other slow work), with the elapsed seconds. The counter is hidden from screen readers
// so a live region does not repeat it.

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

import { useI18n } from "@/shared/i18n/i18n";

export function ModelWaiting({ label, hint }: { label: string; hint?: string }) {
  const { t } = useI18n();
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <span className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
      <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden /> {label}
      {seconds >= 15 && (
        <span className="text-[0.7rem] text-muted-foreground">
          {hint ?? t("slowModelHint")} <span className="tabular-nums" aria-hidden>({t("elapsedSeconds", { seconds })})</span>
        </span>
      )}
    </span>
  );
}
