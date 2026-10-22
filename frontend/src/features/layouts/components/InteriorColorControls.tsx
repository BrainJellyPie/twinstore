import type { InteriorColors, StoreDesign } from "@/shared/types/domain";
import { INTERIOR_COLOR_FIELDS, resolveInteriorPalette } from "@/features/store-viewer/realistic/designThemes";
import { useI18n } from "@/shared/i18n/i18n";
import { COLOR_LABELS, COLOR_RESET_LABELS } from "../optionLabels";

export function InteriorColorControls({ design, colors, onChange }: {
  design?: StoreDesign;
  colors?: InteriorColors | null;
  onChange: (colors: InteriorColors | null) => void;
}) {
  const { t } = useI18n();
  const palette = resolveInteriorPalette(design, colors);
  const count = INTERIOR_COLOR_FIELDS.filter(([key]) => colors?.[key] != null).length;
  return <details className="space-y-2 rounded border p-2 text-xs">
    <summary className="cursor-pointer">{count > 0 ? t("layCustomColorsCount", { count }) : t("layCustomColors")}</summary>
    <p className="text-muted-foreground">{t("layCustomColorsHint")}</p>
    <div className="grid gap-2 sm:grid-cols-2">
      {INTERIOR_COLOR_FIELDS.map(([key]) => <div key={key} className="space-y-1">
        <label className="flex items-center justify-between gap-2">{t(COLOR_LABELS[key])}
          <input type="color" value={palette[key]} className="h-8 w-12 shrink-0 cursor-pointer rounded border bg-background p-0.5"
            onChange={(event) => onChange({ ...colors, [key]: event.target.value })} />
        </label>
        <div className="flex items-center justify-between gap-2 text-[11px]">
          <code>{palette[key]}</code>
          <button type="button" className="underline disabled:opacity-50" aria-label={t(COLOR_RESET_LABELS[key])}
            disabled={colors?.[key] == null} onClick={() => onChange({ ...colors, [key]: null })}>{t("layUseDesignColor")}</button>
        </div>
      </div>)}
    </div>
    <button type="button" className="rounded border px-2 py-1 disabled:opacity-50" disabled={count === 0}
      onClick={() => onChange(null)}>{t("layResetAllColors")}</button>
  </details>;
}
