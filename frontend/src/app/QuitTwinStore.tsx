// Closing the browser tab leaves TwinStore running: the launcher, the server and the local model stay up in the
// background (holding memory, and keeping the app from being updated or deleted). Under the launcher, the top bar
// carries a Quit button and a one-time notice says so.

import { useState } from "react";
import { Power, TriangleAlert, X } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
import { useI18n } from "@/shared/i18n/i18n";

import { quitLauncher, useLauncher } from "./launcher";

export const TAB_CLOSE_NOTICE_KEY = "twinstore.tabCloseNotice.dismissed";

function noticeDismissed(): boolean {
  try {
    return localStorage.getItem(TAB_CLOSE_NOTICE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Quit button for the top bar; shown only when the app runs under the TwinStore launcher. */
export function QuitButton() {
  const { t } = useI18n();
  const launched = useLauncher();
  const [open, setOpen] = useState(false);
  if (!launched) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="glass flex h-9 shrink-0 items-center gap-1.5 rounded-xl px-2.5 text-sm font-medium transition-colors hover:bg-negative/10 hover:text-negative focus-visible:outline-2 focus-visible:outline-ring"
        aria-label={t("quitTwinStore")}
        title={t("quitButtonTitle")}
      >
        <Power className="size-4" aria-hidden />
        <span className="hidden sm:inline">{t("quitShort")}</span>
      </button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("quitConfirmTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("quitConfirmDescription")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => void quitLauncher({ title: t("quitStoppedTitle"), body: t("quitStoppedBody") })}
            >
              {t("quitTwinStore")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

/** One-time warning, until dismissed in this browser, that closing the tab does not stop TwinStore. */
export function TabCloseNotice() {
  const { t } = useI18n();
  const launched = useLauncher();
  const [dismissed, setDismissed] = useState(noticeDismissed);
  if (!launched || dismissed) return null;

  const dismiss = () => {
    setDismissed(true);
    try {
      localStorage.setItem(TAB_CLOSE_NOTICE_KEY, "1");
    } catch {
      /* storage blocked: hidden for this page only */
    }
  };

  return (
    <div role="note" className="relative z-20 px-4 pt-2">
      <div className="glass relative mx-auto flex max-w-6xl items-start gap-3 rounded-2xl border-l-2 border-l-warn px-3 py-2.5 text-sm">
        <span className="tone-warn mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg text-warn" aria-hidden>
          <TriangleAlert className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium leading-snug">{t("tabCloseNoticeTitle")}</p>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{t("tabCloseNoticeBody")}</p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          className="grid size-8 shrink-0 place-items-center rounded-lg text-muted-foreground hover:bg-foreground/[0.06] hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          aria-label={t("hideNotice")}
          title={t("hideNotice")}
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  );
}
