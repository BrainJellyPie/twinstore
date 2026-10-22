// The create-store form filled from one description: the text model fills only what the description says (an address
// only when one is given) and picks the starting store format from the generator's list. Every field stays editable.

import { useId, useLayoutEffect, useRef, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import * as api from "@/shared/api/client";
import { useI18n } from "@/shared/i18n/i18n";

export function DescribeStoreField({ disabled, formKey, onFilled }: {
  disabled?: boolean;
  /** Changes whenever the form changes; an answer requested before that is dropped so it cannot overwrite edits. */
  formKey: string;
  onFilled: (draft: api.StoreSetupDraft) => void;
}) {
  const { t, locale } = useI18n();
  const id = useId();
  const [text, setText] = useState("");
  // Plain state rather than a query mutation: the wizard also renders outside the app's query provider.
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filled, setFilled] = useState<{ text: string; draft: api.StoreSetupDraft } | null>(null);
  const request = useRef(0);
  const length = Array.from(text.trim()).length;
  useLayoutEffect(() => {
    setBusy(false);
    setError(null);
    return () => { request.current += 1; };
  }, [text, formKey, locale, disabled]);
  const fill = async () => {
    if (disabled || busy || length < 5) return;
    const asked = text;
    const current = ++request.current;
    setBusy(true);
    setError(null);
    try {
      const draft = await api.draftStoreSetup({ text: asked.trim(), locale });
      if (current !== request.current) return;
      setFilled({ text: asked, draft });
      onFilled(draft);
    } catch (e) {
      if (current === request.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (current === request.current) setBusy(false);
    }
  };
  const shown = filled?.text === text ? filled.draft : null;

  return (
    <div className="space-y-2 rounded-xl bg-muted/60 p-3">
      <label htmlFor={id} className="flex items-center gap-1.5 text-sm font-medium"><Sparkles className="size-4 text-primary" aria-hidden />{t("describeStore")}</label>
      <textarea id={id} value={text} disabled={disabled} rows={2} onChange={(e) => setText(Array.from(e.target.value).slice(0, 800).join(""))}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.nativeEvent.keyCode !== 229) { e.preventDefault(); void fill(); } }}
        placeholder={t("describeStorePlaceholder")}
        className="w-full resize-none rounded-md border bg-background px-2.5 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/40" />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => void fill()} disabled={disabled || busy || length < 5}
          className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2.5 py-1 text-xs font-medium hover:bg-muted disabled:opacity-50">
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5 text-primary" />}
          {busy ? t("fillingFromDescription") : t("fillFromDescription")}
        </button>
        {shown && <span className="text-xs text-muted-foreground">{t("filledFromDescription")}</span>}
        {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
      </div>
      {shown && shown.warnings.length > 0 && (
        <ul className="space-y-0.5 text-xs text-muted-foreground">{shown.warnings.map((w) => <li key={w}>· {w}</li>)}</ul>
      )}
    </div>
  );
}
