// Why the latest run of this layout failed, until a later run of it completes. Read from the
// run list, so it survives reloads and other tabs and stays with its own layout.

import { useId, useState } from "react";

import { useI18n } from "@/shared/i18n/i18n";
import { useRuns } from "@/shared/queries/useRuns";
import { cn } from "@/shared/utils/cn";

import { latestRunFailure, runFailureMessage } from "../runFailure";

export function LastRunFailure({ projectId, setupId, className }: { projectId: string; setupId: string; className?: string }) {
  const failure = latestRunFailure(useRuns(projectId, setupId).data);
  if (!failure) return null;
  return <FailureNote key={failure.run_id} error={failure.error ?? ""} className={className} />;
}

function FailureNote({ error, className }: { error: string; className?: string }) {
  const { t } = useI18n();
  const id = useId();
  const [expanded, setExpanded] = useState(false);
  const message = runFailureMessage(error);
  const long = message.length > 200 || message.split("\n").length > 3;

  return (
    <div className={className}>
      <p id={id} className={cn("whitespace-pre-wrap [overflow-wrap:anywhere]", long && !expanded && "line-clamp-3")}>
        {message ? t("lastRunFailed", { message }) : t("lastRunFailedNoDetails")}
      </p>
      {long && (
        <button type="button" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded((v) => !v)}
          className="mt-0.5 rounded-sm text-xs font-medium underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-ring">
          {expanded ? t("showLess") : t("showFullMessage")}
        </button>
      )}
    </div>
  );
}
