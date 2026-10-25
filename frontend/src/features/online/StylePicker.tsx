// Pick a page style by seeing the store itself in each one: every card is the saved store's home page, drawn by the
// server in that style.

import { Check } from "lucide-react";

import { PAGE_STYLES, sitePreviewUrl, type PageStyle } from "@/shared/api/online";
import { cn } from "@/shared/utils/cn";
import { useI18n } from "@/shared/i18n/i18n";

import { STYLE_HINTS, STYLE_LABELS } from "./labels";

export function StylePicker({ projectId, siteId, storeName, version, saved, value, onChange }: {
  projectId: string; siteId: string; storeName: string; version: string;
  saved: PageStyle; value: PageStyle; onChange: (style: PageStyle) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6" role="radiogroup" aria-label={t("onStyleTitle")}>
      {PAGE_STYLES.map((style) => {
        const picked = style === value;
        return (
          <button key={style} type="button" role="radio" aria-checked={picked} onClick={() => onChange(style)}
            className={cn("group overflow-hidden rounded-2xl border bg-card text-left transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-lg",
              picked ? "border-primary ring-2 ring-primary/50" : "hover:border-foreground/30")}>
            <div className="relative aspect-[4/3] overflow-hidden bg-muted">
              <img src={sitePreviewUrl(projectId, siteId, "desktop", version, style)} loading="lazy"
                alt={t("onStylePreviewAlt", { store: storeName, style: t(STYLE_LABELS[style]) })}
                className="absolute inset-x-0 top-0 w-full transition-transform duration-500 group-hover:scale-[1.03]"
                // The browser bar of the screenshot is the same in every style; start below it.
                style={{ marginTop: "-7.8%" }} />
              {picked && (
                <span className="absolute top-2 right-2 grid size-6 place-items-center rounded-full bg-primary text-primary-foreground shadow" aria-hidden>
                  <Check className="size-3.5" />
                </span>
              )}
            </div>
            <div className="space-y-0.5 p-2.5">
              <div className="flex items-center gap-1.5 text-sm font-semibold">
                {t(STYLE_LABELS[style])}
                {style === saved ? (
                  <span className="rounded-full bg-muted px-1.5 text-[0.6rem] font-medium text-muted-foreground">{t("onStyleCurrent")}</span>
                ) : picked && (
                  <span className="rounded-full bg-primary/10 px-1.5 text-[0.6rem] font-medium text-primary">{t("onStyleUnsaved")}</span>
                )}
              </div>
              <p className="line-clamp-2 text-[0.7rem] text-muted-foreground">{t(STYLE_HINTS[style])}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
