// Change the layout in words: the text model turns instructions into price, sign, discount, move and category-price
// edits on this layout's products and shelves; the user reviews them and keeps the result as a new layout.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Wand2 } from "lucide-react";

import { applyLayoutEdit, draftLayoutEdit, type LayoutEditDraft } from "@/shared/api/marketing";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { queryKeys } from "@/shared/queries/keys";
import { useAssistStore } from "@/stores/assistStore";
import { useSimulationStore } from "@/stores/simulationStore";

export function LayoutEditInWords({ projectId, setupId }: { projectId: string; setupId: string }) {
  const qc = useQueryClient();
  const setSelectedSetupId = useSimulationStore((s) => s.setSelectedSetupId);
  const [text, setText] = useState("");
  const [name, setName] = useState("");
  const [drafted, setDrafted] = useState<{ text: string; setupId: string; draft: LayoutEditDraft } | null>(null);
  const length = Array.from(text.trim()).length;
  const draft = useMutation({
    mutationFn: (t: string) => draftLayoutEdit(projectId, setupId, t.trim()),
    onSuccess: (d, t) => { setDrafted({ text: t, setupId, draft: d }); setName(d.name); },
  });
  const save = useMutation({
    mutationFn: (d: LayoutEditDraft) => applyLayoutEdit(projectId, setupId, { name: name.trim(), changes: d.changes }),
    onSuccess: async (setup) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: queryKeys.setups(projectId) }),
        qc.invalidateQueries({ queryKey: queryKeys.project(projectId) }),
      ]);
      setDrafted(null);
      setText("");
      setSelectedSetupId(setup.id);
    },
  });
  // Instructions typed in the command palette and routed here are drafted once this layout is open.
  const box = useRef<HTMLDivElement>(null);
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const queueDraft = useQueuedStart(draft.mutate);
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["layout_edit"]);
    if (!routed) return;
    const words = Array.from(routed.text).slice(0, 800).join("");
    setText(words);
    box.current?.scrollIntoView?.({ block: "nearest" });
    queueDraft(words);
  }, [pendingAsk, projectId, takeAsk, queueDraft]);
  // A draft belongs to the words and the layout it was made from.
  const shown = drafted && drafted.text === text && drafted.setupId === setupId ? drafted.draft : null;
  const busy = draft.isPending || save.isPending;
  const request = () => { if (length >= 5 && !busy) { save.reset(); draft.mutate(text); } };

  return (
    <div ref={box} className="mt-3 space-y-2 border-t pt-3">
      <p className="flex items-center gap-1.5 text-xs font-medium"><Wand2 className="size-3.5 text-primary" aria-hidden /> Change it in words</p>
      <textarea value={text} onChange={(e) => setText(Array.from(e.target.value).slice(0, 800).join(""))} rows={2}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); request(); } }}
        placeholder="e.g. Put the cola at eye level, 10 % off all ice cream and a SALE sign on the chips"
        aria-label="Layout changes in words"
        className="w-full resize-none rounded-md border bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
      <Button type="button" size="sm" variant="outline" className="h-7 text-xs" disabled={length < 5 || busy} onClick={request}>
        {draft.isPending ? <Loader2 className="size-3 animate-spin" /> : <Wand2 className="size-3" />} Draft the edits
      </Button>
      {draft.error && <p role="alert" className="text-xs text-destructive">{draft.error.message}</p>}
      {shown && (
        <div className="space-y-2 rounded-md bg-foreground/[0.035] p-2 text-xs">
          {shown.summary && <p className="text-muted-foreground">{shown.summary}</p>}
          {shown.applied.length > 0 ? (
            <ul aria-label="Drafted edits" className="list-disc space-y-0.5 pl-4">
              {shown.applied.map((a) => <li key={a}>{a}</li>)}
            </ul>
          ) : <p>No edit applies to this layout. Reword the instructions and draft again.</p>}
          {shown.warnings.map((w) => <p key={w} className="text-muted-foreground">· {w}</p>)}
          {shown.applied.length > 0 && (
            <>
              <Input value={name} onChange={(e) => setName(e.target.value.slice(0, 80))} placeholder="Name of the new layout"
                aria-label="Name of the new layout" className="h-8 text-xs" />
              <Button type="button" size="sm" className="h-7 text-xs" disabled={busy} onClick={() => save.mutate(shown)}>
                {save.isPending && <Loader2 className="size-3 animate-spin" />} Save as a new layout
              </Button>
              <p className="text-[0.7rem] text-muted-foreground">This layout stays as it is; the new one opens next.</p>
            </>
          )}
          {save.error && <p role="alert" className="text-destructive">{save.error.message}</p>}
        </div>
      )}
    </div>
  );
}
