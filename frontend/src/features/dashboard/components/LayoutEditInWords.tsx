// Change the layout in words: the text model turns instructions into price, sign, discount, move and category-price
// edits on this layout's products and shelves; the user reviews them and keeps the result as a new layout.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Wand2 } from "lucide-react";

import { applyLayoutEdit, draftLayoutEdit, type LayoutEditDraft } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";
import { useI18n } from "@/shared/i18n/i18n";
import { NeedsModel } from "@/features/settings/NeedsModel";

export function LayoutEditInWords({ projectId, setupId }: { projectId: string; setupId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const setSelectedSetupId = useSimulationStore((s) => s.setSelectedSetupId);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const context = JSON.stringify([projectId, setupId, text]);
  const [drafted, setDrafted] = useState<{ context: string; requestId: string; draft: LayoutEditDraft } | null>(null);
  const length = Array.from(text.trim()).length;
  const draft = useMutation({ mutationFn: (t: string) => draftLayoutEdit(projectId, setupId, t.trim()) });
  const save = useMutation({
    mutationFn: (request: { projectId: string; setupId: string; body: Parameters<typeof applyLayoutEdit>[2] }) =>
      applyLayoutEdit(request.projectId, request.setupId, request.body),
    onSuccess: async (_setup, request) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.setups(request.projectId) }),
        qc.invalidateQueries({ queryKey: queryKeys.project(request.projectId) }),
      ]);
    },
  });
  const resetDraft = draft.reset, resetSave = save.reset;
  useLayoutEffect(() => { resetDraft(); resetSave(); }, [context, name, resetDraft, resetSave]);
  const shown = drafted?.context === context ? drafted.draft : null;
  const busy = draft.isPending || save.isPending;
  const request = (words: string, replacePending = false) => {
    if (Array.from(words.trim()).length < 5 || (busy && !replacePending)) return;
    save.reset();
    draft.mutate(words, { onSuccess: (d) => {
      setDrafted({ context: JSON.stringify([projectId, setupId, words]), requestId: crypto.randomUUID().replace(/-/g, ""), draft: d });
      setName(d.name);
    } });
  };
  const persist = () => {
    if (!shown || !drafted || busy) return;
    const selected = useSimulationStore.getState().selectedSetupId;
    save.mutate({ projectId, setupId, body: { name: name.trim(), changes: shown.changes,
      source_sha256: shown.source_sha256, request_id: drafted.requestId } }, { onSuccess: (setup) => {
      if (useSimulationStore.getState().selectedSetupId !== selected) return;
      setDrafted(null);
      setText("");
      setSelectedSetupId(setup.id);
    } });
  };
  // Instructions typed in the command palette and routed here are drafted once this layout is open.
  const box = useRef<HTMLDivElement>(null);
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const queueDraft = useQueuedStart((words: string) => request(words, true));
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["layout_edit"]);
    if (!routed) return;
    const words = Array.from(routed.text).slice(0, 800).join("");
    setText(words);
    box.current?.scrollIntoView?.({ block: "nearest" });
    queueDraft(words);
  }, [pendingAsk, projectId, takeAsk, queueDraft]);

  return (
    <div ref={box} className="mt-3 space-y-2 border-t pt-3">
      <p className="flex items-center gap-1.5 text-xs font-medium"><Wand2 className="size-3.5 text-primary" aria-hidden /> {t("editWordsTitle")}</p>
      <textarea value={text} onChange={(e) => setText(Array.from(e.target.value).slice(0, 800).join(""))} rows={2}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); request(text); } }}
        placeholder={t("editWordsPlaceholder")}
        aria-label={t("editWordsLabel")}
        className="w-full resize-none rounded-md border bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
      <NeedsModel purpose="assist" />
      <Button type="button" size="sm" variant="outline" className="h-7 text-xs" disabled={length < 5 || busy} onClick={() => request(text)}>
        {draft.isPending ? <Loader2 className="size-3 animate-spin" /> : <Wand2 className="size-3" />} {t("editWordsDraft")}
      </Button>
      {draft.error && <p role="alert" className="text-xs text-destructive">{draft.error.message}</p>}
      {shown && (
        <div className="space-y-2 rounded-md bg-foreground/[0.035] p-2 text-xs">
          {shown.summary && <p className="text-muted-foreground">{shown.summary}</p>}
          {shown.applied.length > 0 ? (
            <ul aria-label={t("editWordsDrafted")} className="list-disc space-y-0.5 pl-4">
              {shown.applied.map((a) => <li key={a}>{a}</li>)}
            </ul>
          ) : <p>{t("editWordsNone")}</p>}
          {shown.warnings.map((w) => <p key={w} className="text-muted-foreground">· {w}</p>)}
          {shown.applied.length > 0 && (
            <>
              <Input value={name} onChange={(e) => setName(Array.from(e.target.value).slice(0, 80).join(""))} placeholder={t("editWordsName")}
                aria-label={t("editWordsName")} className="h-8 text-xs" />
              <Button type="button" size="sm" className="h-7 text-xs" disabled={busy} onClick={persist}>
                {save.isPending && <Loader2 className="size-3 animate-spin" />} {t("editWordsSave")}
              </Button>
              <p className="text-[0.7rem] text-muted-foreground">{t("editWordsSaveHint")}</p>
            </>
          )}
          {save.error && <p role="alert" className="text-destructive">{save.error.message}</p>}
        </div>
      )}
    </div>
  );
}
