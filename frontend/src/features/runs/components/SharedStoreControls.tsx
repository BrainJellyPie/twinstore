// The shared store in the run dialog: shoppers take stock from the same shelves and wait at the same tills.

import { useId } from "react";
import { Store as StoreIcon } from "lucide-react";

import { Input } from "@/shared/components/ui/input";
import { useI18n } from "@/shared/i18n/i18n";

import { sharedStoreOptions, wholeIn, type SharedStoreChoice } from "../sharedStore";

/** `fieldsOnly`: the settings without the on/off switch (the operations lab, where the store is always shared). */
export function SharedStoreControls({ value, onChange, tillsInLayout, fieldsOnly = false }: {
  value: SharedStoreChoice;
  onChange: (next: SharedStoreChoice) => void;
  tillsInLayout?: number;
  fieldsOnly?: boolean;
}) {
  const { t } = useI18n();
  const set = (patch: Partial<SharedStoreChoice>) => onChange({ ...value, ...patch });
  const id = useId();
  const invalid = sharedStoreOptions(value) === "invalid";
  // With a crew the same staff work the tills and refill the shelves: no refill rounds or separate tills to set.
  const crew = value.crew.trim() !== "";
  const field = "space-y-1";
  return (
    <div className={fieldsOnly ? "space-y-2 text-xs" : "space-y-2 rounded-md border p-3 text-xs"}>
      {!fieldsOnly && <>
      <label className="flex items-start gap-2 text-sm font-medium" htmlFor={`${id}-on`}>
        <input id={`${id}-on`} type="checkbox" className="mt-0.5 size-4 accent-primary" checked={value.enabled}
          onChange={(e) => set({ enabled: e.target.checked })} aria-describedby={`${id}-hint`} />
        <StoreIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>{t("opsShareTitle")}</span>
      </label>
      <p id={`${id}-hint`} className="text-muted-foreground">{t("opsShareHint")}</p>
      </>}
      {value.enabled && (
        <div className="grid grid-cols-1 gap-2 min-[400px]:grid-cols-2">
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-stock`}>{t("opsStockPerFacing")}</label>
            <Input id={`${id}-stock`} type="number" min={1} max={10000} step={1} className="h-7" value={value.stock}
              onChange={(e) => set({ stock: e.target.value })} aria-invalid={wholeIn(value.stock, 1, 10_000) === null} />
          </div>
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-crew`}>{t("opsCrew")}</label>
            <Input id={`${id}-crew`} type="number" min={1} max={100} step={1} className="h-7" value={value.crew}
              onChange={(e) => set({ crew: e.target.value })} aria-describedby={`${id}-crew-hint`}
              aria-invalid={value.crew.trim() !== "" && wholeIn(value.crew, 1, 100) === null} />
            <p id={`${id}-crew-hint`} className="text-muted-foreground">{t("opsCrewHint")}</p>
          </div>
          {crew ? (
            <div className={field}>
              <label className="block font-medium" htmlFor={`${id}-refill-at`}>{t("opsRefillAt")}</label>
              <Input id={`${id}-refill-at`} type="number" min={0} max={95} step={5} className="h-7" value={value.refillAt}
                onChange={(e) => set({ refillAt: e.target.value })} aria-describedby={`${id}-refill-at-hint`}
                aria-invalid={wholeIn(value.refillAt, 0, 95) === null} />
              <p id={`${id}-refill-at-hint`} className="text-muted-foreground">{t("opsRefillAtHint")}</p>
            </div>
          ) : <>
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-restock`}>{t("opsRestockEvery")}</label>
            <Input id={`${id}-restock`} type="number" min={5} max={1440} step={5} className="h-7" value={value.restock}
              onChange={(e) => set({ restock: e.target.value })} aria-describedby={`${id}-restock-hint`}
              aria-invalid={value.restock.trim() !== "" && wholeIn(value.restock, 5, 1440) === null} />
            <p id={`${id}-restock-hint`} className="text-muted-foreground">{t("opsRestockBlank")}</p>
          </div>
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-tills`}>{t("opsTillsOpen")}</label>
            <Input id={`${id}-tills`} type="number" min={1} max={50} step={1} className="h-7" value={value.tills}
              placeholder={tillsInLayout ? String(tillsInLayout) : undefined} onChange={(e) => set({ tills: e.target.value })}
              aria-describedby={`${id}-tills-hint`}
              aria-invalid={value.tills.trim() !== "" && wholeIn(value.tills, 1, 50) === null} />
            <p id={`${id}-tills-hint`} className="text-muted-foreground">{t("opsTillsBlank")}</p>
          </div>
          </>}
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-patience`}>{t("opsPatience")}</label>
            <Input id={`${id}-patience`} type="number" min={0.5} max={120} step={0.5} className="h-7" value={value.patience}
              onChange={(e) => set({ patience: e.target.value })} aria-describedby={`${id}-patience-hint`} />
            <p id={`${id}-patience-hint`} className="text-muted-foreground">{t("opsPatienceHint")}</p>
          </div>
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-crowd`}>{t("opsCrowd")}</label>
            <Input id={`${id}-crowd`} type="number" min={2} max={50} step={1} className="h-7" value={value.crowd}
              onChange={(e) => set({ crowd: e.target.value })} aria-describedby={`${id}-crowd-hint`}
              aria-invalid={value.crowd.trim() !== "" && wholeIn(value.crowd, 2, 50) === null} />
            <p id={`${id}-crowd-hint`} className="text-muted-foreground">{t("opsCrowdHint")}</p>
          </div>
          <div className={field}>
            <label className="block font-medium" htmlFor={`${id}-backroom`}>{t("opsBackroom")}</label>
            <Input id={`${id}-backroom`} type="number" min={0} max={1000000} step={1} className="h-7" value={value.backroom}
              onChange={(e) => set({ backroom: e.target.value })} aria-describedby={`${id}-backroom-hint`}
              aria-invalid={value.backroom.trim() !== "" && wholeIn(value.backroom, 0, 1_000_000) === null} />
            <p id={`${id}-backroom-hint`} className="text-muted-foreground">{t("opsBackroomHint")}</p>
          </div>
          {value.backroom.trim() !== "" && (
            <label className="flex items-center gap-2 self-start pt-5" htmlFor={`${id}-delivery`}>
              <input id={`${id}-delivery`} type="checkbox" className="size-4 accent-primary" checked={value.delivery}
                onChange={(e) => set({ delivery: e.target.checked })} />
              {t("opsDelivery")}
            </label>
          )}
        </div>
      )}
      {invalid && <p role="alert" className="text-destructive">{t("opsInvalid")}</p>}
    </div>
  );
}
