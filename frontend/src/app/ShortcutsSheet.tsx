// The keys that work without the mouse, opened with ? anywhere (outside a text field) or from the command palette.

import { Fragment, useEffect } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/shared/components/ui/dialog";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

import { MOD_KEY, useShortcutsSheet } from "./commandPalette";

const SHORTCUTS: { keys: (string | MessageKey)[][]; label: MessageKey }[] = [
  { keys: [[MOD_KEY, "K"], ["/"]], label: "kbPalette" },
  { keys: [["↑", "↓", "↵"]], label: "kbPaletteMove" },
  { keys: [["kbSpace"]], label: "kbPlay" },
  { keys: [["←", "→"]], label: "kbSeek" },
  { keys: [["Esc"]], label: "kbClose" },
  { keys: [["?"]], label: "kbShow" },
];

export function ShortcutsSheet() {
  const { t } = useI18n();
  const open = useShortcutsSheet((s) => s.open);
  const setOpen = useShortcutsSheet((s) => s.setOpen);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key !== "?" || e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
      if (el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName))) return;
      e.preventDefault();
      setOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("kbTitle")}</DialogTitle>
          <DialogDescription>{t("kbIntro")}</DialogDescription>
        </DialogHeader>
        <dl className="divide-y text-sm">
          {SHORTCUTS.map(({ keys, label }) => (
            <div key={label} className="flex items-center justify-between gap-4 py-2.5">
              <dt>{t(label)}</dt>
              <dd className="flex shrink-0 flex-wrap items-center justify-end gap-1 text-xs text-muted-foreground">
                {keys.map((combo, i) => (
                  <Fragment key={i}>
                    {i > 0 && <span className="px-0.5">{t("kbOr")}</span>}
                    {combo.map((k) => (
                      <kbd key={k} className="num min-w-6 rounded-md border bg-foreground/[0.04] px-1.5 py-0.5 text-center text-foreground">
                        {k.startsWith("kb") ? t(k as MessageKey) : k}
                      </kbd>
                    ))}
                  </Fragment>
                ))}
              </dd>
            </div>
          ))}
        </dl>
      </DialogContent>
    </Dialog>
  );
}
