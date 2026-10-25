// Change a store's design by asking for it. A text model reads the conversation and the design being edited and
// answers with the options it changed; they go straight into the designer's draft (one click undoes them), the
// preview shows the store before and after, and the draft can be saved as a variant and tested against the store.

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { FlaskConical, Loader2, RotateCcw, Send, Sparkles, Undo2, Wand2 } from "lucide-react";

import * as api from "@/shared/api/client";
import { designChat, draftPreview, onlineKeys, sitePreviewUrl, type DesignMessage, type Device, type OnlineSite, type SiteOptions } from "@/shared/api/online";
import { Button } from "@/shared/components/ui/button";
import { queryKeys } from "@/shared/queries/keys";
import { cn } from "@/shared/utils/cn";
import { useQueuedStart } from "@/shared/hooks/useQueuedStart";
import { useAssistStore } from "@/stores/assistStore";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

// The designer's own field names for what the model may change.
const OPTION_LABELS: Partial<Record<keyof SiteOptions, MessageKey>> = {
  page_style: "onStyleTitle", theme_color: "onOptTheme", grid_columns: "onOptColumns", products_per_page: "onOptPerPage",
  hero_banner: "onOptHero", hero_text: "onOptHeroText", home_sections: "onOptSections", large_text: "onOptLargeText",
  show_ratings: "onOptRatings", default_sort: "onOptSort", quick_add: "onOptQuickAdd", wishlist: "onOptWishlist",
  urgency: "onOptUrgency", social_proof: "onOptSocial", welcome_popup: "onOptPopup", cookie_banner: "onOptCookies",
  chat_widget: "onOptChat", trust_badges: "onOptTrust", shipping_fee: "onOptShipping", free_shipping_threshold: "onOptFreeOver",
  coupon_code: "onOptCouponCode", coupon_percent: "onOptCouponPercent", guest_checkout: "onOptGuest", checkout_flow: "onOptFlow",
  one_click_buy: "onOptOneClick", page_load_ms: "onOptLoad",
};
const IDEAS: MessageKey[] = ["onAiIdeaPremium", "onAiIdeaKids", "onAiIdeaCalm", "onAiIdeaCheckout", "onAiIdeaNeon"];

interface Turn extends DesignMessage { before?: SiteOptions; undone?: boolean }

export function DesignChat({ projectId, site, options, onOptions, onTest, testing, testError }: {
  projectId: string; site: OnlineSite; options: SiteOptions; onOptions: (options: SiteOptions) => void;
  /** Save the draft as a variant and open a comparison run with the store. */
  onTest: (note: string) => void; testing: boolean; testError: string;
}) {
  const { t } = useI18n();
  const { data: models = [] } = useQuery({ queryKey: queryKeys.models(), queryFn: ({ signal }) => api.getModels(signal), staleTime: 60_000 });
  const [model, setModel] = useState("");
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [view, setView] = useState<"after" | "before">("after");
  const [device, setDevice] = useState<Device>("desktop");
  const end = useRef<HTMLDivElement>(null);
  const edited = JSON.stringify(options) !== JSON.stringify(site.options);
  const ask = useMutation({
    mutationFn: (owner: string) => designChat(projectId, site.id, {
      messages: [...turns.map(({ role, text: said, changed }) => ({ role, text: said, changed })), { role: "owner", text: owner }],
      options, model: model || undefined,
    }),
    onMutate: () => setText(""),
    onSuccess: (reply, owner) => {
      setTurns((all) => [...all, { role: "owner", text: owner },
        { role: "designer", text: reply.reply, changed: reply.changed, before: reply.changed.length ? options : undefined }]);
      if (reply.changed.length) { onOptions(reply.options); setView("after"); }
    },
    onError: (_e, owner) => setText((current) => current || owner),
  });
  const preview = useQuery({
    queryKey: onlineKeys.draftPreview(projectId, site.id, options, device),
    queryFn: ({ signal }) => draftPreview(projectId, site.id, options, device, signal),
    enabled: edited && view === "after",
    staleTime: Infinity,
  });
  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [turns.length, ask.isPending]);
  const send = (said: string) => {
    const owner = said.trim();
    if (owner && !ask.isPending) ask.mutate(owner);
  };
  // A request typed in the command palette and routed here is sent once the designer is open.
  const pendingAsk = useAssistStore((s) => s.pending);
  const takeAsk = useAssistStore((s) => s.take);
  const queueSend = useQueuedStart((said: string) => send(said));
  useEffect(() => {
    if (!pendingAsk) return;
    const routed = takeAsk(projectId, ["online_design"]);
    if (routed) queueSend(Array.from(routed.text).slice(0, 1200).join(""));
  }, [pendingAsk, projectId, takeAsk, queueSend]);
  const undo = (index: number) => {
    const turn = turns[index];
    if (!turn?.before) return;
    onOptions(turn.before);
    setTurns((all) => all.map((x, i) => (i >= index && x.before ? { ...x, undone: true } : x)));
  };
  const lastOwner = [...turns].reverse().find((x) => x.role === "owner")?.text ?? "";
  const src = edited && view === "after" ? preview.data : sitePreviewUrl(projectId, site.id, device, site.updated_at);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="flex min-h-[22rem] flex-col gap-2">
        <div className="flex-1 space-y-2 overflow-y-auto rounded-2xl border bg-muted/30 p-3" aria-live="polite">
          {turns.length === 0 && !ask.isPending && (
            <div className="space-y-2 text-xs text-muted-foreground">
              <p>{t("onAiEmpty")}</p>
              <div className="flex flex-wrap gap-1.5">
                {IDEAS.map((idea) => (
                  <button key={idea} type="button" onClick={() => send(t(idea))}
                    className="rounded-full border bg-card px-2.5 py-1 text-[0.72rem] text-foreground transition-colors hover:border-primary hover:text-primary">
                    <Sparkles className="mr-1 inline size-3" aria-hidden />{t(idea)}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((turn, i) => turn.role === "owner" ? (
            <p key={i} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3 py-2 text-sm text-primary-foreground">{turn.text}</p>
          ) : (
            <div key={i} className={cn("w-fit max-w-[92%] space-y-1.5 rounded-2xl rounded-bl-md border bg-card px-3 py-2 text-sm", turn.undone && "opacity-60")}>
              <p>{turn.text}</p>
              {(turn.changed?.length ?? 0) === 0 && <p className="text-[0.7rem] text-muted-foreground">{t("onAiNoChange")}</p>}
              {(turn.changed?.length ?? 0) > 0 && (
                <div className="flex flex-wrap items-center gap-1">
                  {turn.changed!.map((key) => (
                    <span key={key} className="rounded-full bg-primary/10 px-2 py-0.5 text-[0.68rem] font-medium text-primary">
                      {OPTION_LABELS[key as keyof SiteOptions] ? t(OPTION_LABELS[key as keyof SiteOptions]!) : key}
                    </span>
                  ))}
                  {turn.before && !turn.undone && (
                    <button type="button" onClick={() => undo(i)} className="ml-1 inline-flex items-center gap-1 text-[0.7rem] text-muted-foreground hover:text-foreground">
                      <Undo2 className="size-3" aria-hidden /> {t("onAiUndo")}
                    </button>
                  )}
                  {turn.undone && <span className="text-[0.7rem] text-muted-foreground">{t("onAiUndone")}</span>}
                </div>
              )}
            </div>
          ))}
          {ask.isPending && (
            <p className="flex w-fit items-center gap-2 rounded-2xl border bg-card px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" aria-hidden /> {t("onAiThinking")}
            </p>
          )}
          <div ref={end} />
        </div>
        {ask.error && <p role="alert" className="text-xs text-destructive">{ask.error.message}</p>}
        <form className="flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <textarea value={text} onChange={(e) => setText(e.target.value.slice(0, 1200))} rows={2}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(text); } }}
            placeholder={t("onAiPlaceholder")} aria-label={t("onAiPlaceholder")}
            className="min-h-[2.75rem] flex-1 resize-none rounded-xl border bg-card px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50" />
          <Button type="submit" size="icon" className="size-11 rounded-xl" disabled={!text.trim() || ask.isPending} aria-label={t("onAiSend")} title={t("onAiSend")}>
            {ask.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
          </Button>
        </form>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select value={model} onChange={(e) => setModel(e.target.value)} className="h-7 min-w-0 rounded-lg border bg-card/60 px-1.5" aria-label={t("model")}>
            <option value="">{t("interviewAppModel")}</option>
            {models.map((m) => <option key={m.ref} value={m.ref}>{m.label}</option>)}
          </select>
          {turns.length > 0 && (
            <button type="button" onClick={() => setTurns([])} className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
              <RotateCcw className="size-3" aria-hidden /> {t("onAiNewChat")}
            </button>
          )}
        </div>
      </div>

      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-full border bg-card/60 p-0.5 text-xs" role="group" aria-label={t("onAiPreview")}>
            {(["before", "after"] as const).map((v) => (
              <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)} disabled={v === "after" && !edited}
                className={cn("rounded-full px-3 py-1 disabled:opacity-40", view === v ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
                {v === "before" ? t("onAiBefore") : t("onAiAfter")}
              </button>
            ))}
          </div>
          <div className="inline-flex rounded-full border bg-card/60 p-0.5 text-xs" role="group" aria-label={t("onOptDevice")}>
            {(["desktop", "mobile"] as const).map((d) => (
              <button key={d} type="button" aria-pressed={device === d} onClick={() => setDevice(d)}
                className={cn("rounded-full px-3 py-1", device === d ? "bg-primary text-primary-foreground" : "hover:bg-muted")}>
                {d === "desktop" ? t("onDeviceDesktop") : t("onDeviceMobile")}
              </button>
            ))}
          </div>
          {edited && <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[0.68rem] font-medium text-amber-700 dark:text-amber-300">{t("onAiUnsaved")}</span>}
        </div>
        <div className={cn("relative overflow-hidden rounded-2xl border bg-muted", device === "mobile" ? "mx-auto h-[26rem] w-56" : "h-[26rem]")}>
          {src ? (
            <img src={src} alt={view === "after" && edited ? t("onAiAfterAlt", { store: site.name }) : t("onAiBeforeAlt", { store: site.name })}
              className="absolute inset-x-0 top-0 w-full" style={{ marginTop: device === "desktop" ? "-7.8%" : "-18.6%" }} />
          ) : (
            <p className="grid h-full place-items-center text-xs text-muted-foreground">
              {preview.isError ? preview.error.message : <Loader2 className="size-5 animate-spin" aria-label={t("studioLoading")} />}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => onTest(lastOwner)} disabled={!edited || testing} className="gap-1.5">
            {testing ? <Loader2 className="animate-spin" aria-hidden /> : <FlaskConical aria-hidden />} {t("onAiTest")}
          </Button>
          <span className="flex items-center gap-1 text-[0.7rem] text-muted-foreground"><Wand2 className="size-3" aria-hidden />{t("onAiTestHint")}</span>
        </div>
        {testError && <p role="alert" className="text-xs text-destructive">{testError}</p>}
      </div>
    </div>
  );
}
