import { useEffect } from "react";
import { MessageSquareText, X } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { resolveImageUrl } from "@/shared/api/images";
import type { Face, Rack, SlotItem } from "@/shared/types/domain";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const FACE_LABEL: Record<Face, MessageKey> = { N: "dirNorth", S: "dirSouth", E: "dirEast", W: "dirWest" };
const FACE_ORDER: Face[] = ["N", "S", "E", "W"];

interface Props {
  rack: Rack;
  open: boolean;
  onClose: () => void;
  /** When given (a finished run), offers to ask the run analyst about this shelf. */
  onAsk?: () => void;
}

function lockedFaceSet(rack: Rack): Set<Face> {
  const set = new Set<Face>();
  for (const lf of rack.locked_faces) {
    set.add(lf.face);
  }
  return set;
}

function itemsByLevel(rack: Rack, face: Face): Map<number, SlotItem[]> {
  const out = new Map<number, SlotItem[]>();
  for (const slot of rack.slots) {
    if (slot.face !== face) continue;
    const list = out.get(slot.level) ?? [];
    for (const it of slot.items) list.push(it);
    out.set(slot.level, list);
  }
  return out;
}

function itemCountByFace(rack: Rack): Record<Face, number> {
  const counts: Record<Face, number> = { N: 0, S: 0, E: 0, W: 0 };
  for (const slot of rack.slots) {
    counts[slot.face] += slot.items.length;
  }
  return counts;
}

function FaceContent({ rack, face }: { rack: Rack; face: Face }) {
  const { t } = useI18n();
  const byLevel = itemsByLevel(rack, face);
  const levels: number[] = [];
  for (let lv = rack.levels; lv >= 1; lv -= 1) levels.push(lv);

  return (
    <div className="flex flex-col gap-3">
      {levels.map((level) => {
        const items = byLevel.get(level) ?? [];
        return (
          <div key={level} className="flex items-start gap-3 border-b pb-2 last:border-b-0">
            <div className="w-16 shrink-0 pt-1 text-xs text-muted-foreground">{t("rackLevel", { level })}</div>
            <div className="flex flex-1 flex-wrap gap-2">
              {items.length === 0 ? (
                <div className="text-xs italic text-muted-foreground">{t("rackNoItems")}</div>
              ) : (
                items.map((item, idx) => (
                  <div
                    key={`${item.sku}-${idx}`}
                    className="flex w-20 flex-col items-center gap-1"
                  >
                    {item.image_url ? (
                      <img
                        src={resolveImageUrl(item.image_url)}
                        alt={item.name}
                        className="size-16 rounded border bg-muted object-contain"
                      />
                    ) : (
                      <div className="flex size-16 items-center justify-center rounded border bg-muted text-[0.72rem] text-muted-foreground">
                        {t("rackNoImage")}
                      </div>
                    )}
                    <div className="line-clamp-2 text-center text-xs" title={item.name}>{item.name}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function RackDetailPanel({ rack, open, onClose, onAsk }: Props) {
  const { t } = useI18n();
  const locked = lockedFaceSet(rack);
  const visibleFaces = FACE_ORDER.filter((f) => !locked.has(f));
  const faceCounts = itemCountByFace(rack);
  const defaultFace =
    visibleFaces.find((f) => faceCounts[f] > 0) ?? visibleFaces[0] ?? "N";

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      // An Escape that closed a dialog or menu over the panel (they mark it handled) leaves the panel open.
      if (e.key === "Escape" && !e.defaultPrevented) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label={rack.rack_name || rack.id}
      className="absolute right-4 top-24 z-20 w-[460px] max-w-[90vw] rounded-lg border bg-background/95 p-4 shadow-md backdrop-blur-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{rack.rack_name || rack.id}</h2>
        {onAsk && (
          <button type="button" onClick={onAsk} className="mr-auto inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-primary hover:bg-primary/[0.07]">
            <MessageSquareText className="size-3.5" aria-hidden /> {t("rackAsk")}
          </button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="size-7 p-0"
          onClick={onClose}
          aria-label={t("close")}
        >
          <X className="size-4" />
        </Button>
      </div>

      {visibleFaces.length === 0 ? (
        <div className="text-xs italic text-muted-foreground">
          {t("rackAllBlocked")}
        </div>
      ) : (
        <Tabs key={rack.id} defaultValue={defaultFace} className="w-full">
          <TabsList>
            {visibleFaces.map((f) => (
              <TabsTrigger key={f} value={f} className="text-xs">
                {t(FACE_LABEL[f])} ({faceCounts[f]})
              </TabsTrigger>
            ))}
          </TabsList>
          {visibleFaces.map((f) => (
            <TabsContent key={f} value={f} className="mt-3">
              <FaceContent rack={rack} face={f} />
            </TabsContent>
          ))}
        </Tabs>
      )}
    </div>
  );
}
