// What shoppers said (a group interview) or what the run analyst answered, turned into up to three test questions;
// picking one opens the Marketing studio with that test drafted from the question. Nothing runs on its own.

import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { FlaskConical, Loader2 } from "lucide-react";

import { suggestTests, type TestIdea } from "@/shared/api/interview";
import { useAssistStore } from "@/stores/assistStore";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const KIND_LABEL: Record<TestIdea["kind"], MessageKey> = { ab_test: "testKindAb", shelf_test: "testKindShelf", concept_test: "testKindConcept" };

export function TestIdeas({ projectId, runId, source, groupId }: {
  projectId: string; runId: string; source: "group" | "analyst"; groupId?: string;
}) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const sendAsk = useAssistStore((s) => s.send);
  // Plain state: the panels this sits in also render in tests without a query provider for this call.
  const [ideas, setIdeas] = useState<TestIdea[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      setIdeas(await suggestTests(projectId, runId, source === "group" ? { source, group_id: groupId } : { source }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const pick = (idea: TestIdea) => {
    sendAsk({ projectId, destination: idea.kind, text: idea.question });
    void navigate({ to: "/marketing/$pid", params: { pid: projectId } });
  };

  return (
    <div className="space-y-1.5">
      {!ideas && (
        <button type="button" onClick={() => void load()} disabled={busy}
          className="inline-flex items-center gap-1 text-[0.72rem] text-primary hover:underline disabled:opacity-60">
          {busy ? <Loader2 className="size-3 animate-spin" /> : <FlaskConical className="size-3" />}
          {busy ? t("testWriting") : t("testTurnInto")}
        </button>
      )}
      {error && <p role="alert" className="text-[0.7rem] text-destructive">{error}</p>}
      {ideas && ideas.length === 0 && <p className="text-[0.7rem] text-muted-foreground">{t("testNothing")}</p>}
      {ideas && ideas.length > 0 && (
        <ul className="space-y-1" aria-label={t("testToRun")}>
          {ideas.map((idea) => (
            <li key={idea.question}>
              <button type="button" onClick={() => pick(idea)}
                className="w-full rounded-xl border px-2.5 py-1.5 text-left transition-colors hover:border-primary/60">
                <span className="block text-[0.74rem]">{idea.question}</span>
                <span className="block text-[0.7rem] text-muted-foreground">{t(KIND_LABEL[idea.kind])}{idea.why ? ` · ${idea.why}` : ""} · {t("testOpensDraft")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
