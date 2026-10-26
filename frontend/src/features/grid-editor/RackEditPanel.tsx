// Behavior contract:
//   - All changes propagate to the parent via onChange(patch); the panel owns no
//     submit/apply/delete button.
//   - onChange(null) signals "remove all racks at selectedCell" (trash icon).
//   - Radio / Select emit immediately; text inputs emit only on blur / Enter (perf).
//   - flushPendingText() ref lets the parent force-commit text on Save.

import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  useEffect,
} from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Trash2 } from "lucide-react";
import { Card } from "@/shared/components/ui/card";
import { Input } from "@/shared/components/ui/input";
import { Button } from "@/shared/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/shared/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { Position, RackType } from "@/shared/types/domain";
import { rackDiningSeats } from "@/shared/utils/dining";
import { rackBounds } from "@/shared/utils/grid";
import type { EditorRack } from "./types";
import { RackPreview } from "./RackPreview";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

// UI-only radio identifier.
// - rack    : shelf / fridge — branched via the design dropdown
// - counter : counter — branched via the design dropdown
// - gate    : entrance / exit / both — branched via the gateConfig select
//             (a single cell may hold both entrance + exit racks)
type UiKind = "gate" | "rack" | "counter" | "table";

// A cell may legitimately hold entrance + exit racks together (backend allows it).
export type GateConfig = "entrance" | "exit" | "both";

const GATE_CONFIGS: Array<{ key: GateConfig; label: MessageKey }> = [
  { key: "entrance", label: "rackEditEntranceOnly" },
  { key: "exit", label: "rackEditExitOnly" },
  { key: "both", label: "optScopeBoth" },
];

type RackDesignKey = "shelf_a" | "shelf_b" | "shelf_c" | "fridge_a" | "fridge_b";
type CounterDesignKey = "counter_a" | "counter_b";

interface DesignOption<K extends string> {
  key: K;
  label: MessageKey;
  type: RackType;
  design_variant: "a" | "b" | "c";
}

const RACK_DESIGNS: DesignOption<RackDesignKey>[] = [
  { key: "shelf_a", label: "rackEditOpenA", type: "shelf", design_variant: "a" },
  { key: "shelf_b", label: "rackEditOpenB", type: "shelf", design_variant: "b" },
  { key: "shelf_c", label: "rackEditOpenC", type: "shelf", design_variant: "c" },
  { key: "fridge_a", label: "rackEditDoorA", type: "fridge", design_variant: "a" },
  { key: "fridge_b", label: "rackEditDoorB", type: "fridge", design_variant: "b" },
];

const COUNTER_DESIGNS: DesignOption<CounterDesignKey>[] = [
  { key: "counter_a", label: "rackEditCounterA", type: "counter", design_variant: "a" },
  {
    key: "counter_b",
    label: "rackEditCounterB",
    type: "counter",
    design_variant: "b",
  },
];

const ROTATIONS: Array<0 | 90 | 180 | 270> = [0, 90, 180, 270];

// Derive the UI state (radio kind, design key, gate config) from selectedCellRacks.
// In the gate case the cell may host two racks, so we have to inspect them all.
function deriveUiState(racks: EditorRack[]): {
  kind: UiKind;
  rackDesign: RackDesignKey;
  counterDesign: CounterDesignKey;
  gateConfig: GateConfig;
} | null {
  if (racks.length === 0) return null;
  const hasEntrance = racks.some((r) => r.type === "entrance");
  const hasExit = racks.some((r) => r.type === "exit");
  if (hasEntrance || hasExit) {
    const gateConfig: GateConfig =
      hasEntrance && hasExit ? "both" : hasEntrance ? "entrance" : "exit";
    return { kind: "gate", rackDesign: "shelf_a", counterDesign: "counter_a", gateConfig };
  }
  // Non-gate types assume a single rack at the cell.
  const rack = racks[0]!;
  if (rack.type === "table") return { kind: "table", rackDesign: "shelf_a", counterDesign: "counter_a", gateConfig: "entrance" };
  const variant: "a" | "b" | "c" = rack.design_variant ?? "a";
  if (rack.type === "counter") {
    return {
      kind: "counter",
      rackDesign: "shelf_a",
      counterDesign: variant === "b" ? "counter_b" : "counter_a",
      gateConfig: "entrance",
    };
  }
  const rackKey: RackDesignKey =
    rack.type === "fridge"
      ? variant === "b"
        ? "fridge_b"
        : "fridge_a"
      : variant === "c"
        ? "shelf_c"
        : variant === "b"
          ? "shelf_b"
          : "shelf_a";
  return { kind: "rack", rackDesign: rackKey, counterDesign: "counter_a", gateConfig: "entrance" };
}

export interface RackEditPanelHandle {
  flushPendingText(): void;
}

export interface RackEditPanelProps {
  selectedCell: Position | null;
  /** All racks present at the cell (0–2 in gate case, 0–1 otherwise). */
  selectedCellRacks: EditorRack[];
  /** Single edit target (name/design/rotation). In gate case: first gate rack or null. */
  selectedRack: EditorRack | null;
  onChange: (patch: Partial<EditorRack> | null) => void;
  /** Toggle gate mode / config. Parent owns entrance/exit rack add/remove. */
  onGateConfigChange: (config: GateConfig) => void;
  onMove?: (offset: Position) => void;
  placing?: boolean;
  onPlacementChange?: (placing: boolean) => void;
}

export const RackEditPanel = forwardRef<RackEditPanelHandle, RackEditPanelProps>(
  function RackEditPanel(
    { selectedCell, selectedCellRacks, selectedRack, onChange, onGateConfigChange, onMove, placing = false, onPlacementChange },
    ref,
  ) {
    const { t } = useI18n();
    // Local state for the text input — synced when selectedRack changes.
    // Keystrokes do not emit; emission happens only on blur / Enter / flushPendingText.
    const [nameLocal, setNameLocal] = useState<string>(selectedRack?.rack_name ?? "");
    // Last text emitted to the parent — used to dedupe in flush.
    const lastEmittedName = useRef<string>(selectedRack?.rack_name ?? "");

    // Re-sync when selectedRack identity changes (different cell). Resets lastEmitted
    // because we haven't emitted anything for the new rack yet.
    useEffect(() => {
      const next = selectedRack?.rack_name ?? "";
      setNameLocal(next);
      lastEmittedName.current = next;
      // Re-sync only when the selected rack identity changes (different cell).
      // Depending on rack_name would re-sync mid-edit after our own onChange.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedRack?.id]);

    function commitName(value: string) {
      if (value === lastEmittedName.current) return;
      lastEmittedName.current = value;
      onChange({ rack_name: value });
    }

    useImperativeHandle(
      ref,
      () => ({
        flushPendingText() {
          if (selectedRack == null) return;
          commitName(nameLocal);
        },
      }),
      // commitName only uses closure capture — issue a new handle when nameLocal/selectedRack change.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [nameLocal, selectedRack],
    );

    // selectedCell set with no rack yet → awaiting Type selection.
    // Only the Type radio is active; name/design/rotation are hidden.
    const cellSelected = selectedCell != null;
    const hasAnyRack = selectedCellRacks.length > 0;
    const ui = deriveUiState(selectedCellRacks);
    const kind: UiKind | null = ui?.kind ?? null;
    const rackDesign: RackDesignKey = ui?.rackDesign ?? "shelf_a";
    const counterDesign: CounterDesignKey = ui?.counterDesign ?? "counter_a";
    const gateConfig: GateConfig = ui?.gateConfig ?? "entrance";
    const rotation: 0 | 90 | 180 | 270 = selectedRack?.rotation ?? 0;

    const showNameAndDesign = kind === "rack" || kind === "counter" || kind === "table";
    const showGateConfig = kind === "gate";

    function handleKindChange(next: UiKind) {
      if (next === "table") {
        onChange({ type: "table", shape: [[1, 1], [1, 1]], slots: [], locked_faces: [], design_variant: "a" });
        return;
      }
      if (next === "gate") {
        // Entering gate mode — parent handles entrance/exit add/remove.
        // Default to entrance-only.
        onGateConfigChange("entrance");
        return;
      }
      if (next === "counter") {
        const opt = COUNTER_DESIGNS.find((d) => d.key === counterDesign) ?? COUNTER_DESIGNS[0]!;
        onChange({ type: opt.type, shape: [[1]], design_variant: opt.design_variant });
        return;
      }
      // rack
      const opt = RACK_DESIGNS.find((d) => d.key === rackDesign) ?? RACK_DESIGNS[0]!;
      onChange({ type: opt.type, shape: [[1]], design_variant: opt.design_variant });
    }

    function handleRackDesignChange(key: RackDesignKey) {
      const opt = RACK_DESIGNS.find((d) => d.key === key) ?? RACK_DESIGNS[0]!;
      onChange({ type: opt.type, design_variant: opt.design_variant });
    }

    function handleCounterDesignChange(key: CounterDesignKey) {
      const opt = COUNTER_DESIGNS.find((d) => d.key === key) ?? COUNTER_DESIGNS[0]!;
      onChange({ type: opt.type, design_variant: opt.design_variant });
    }

    function handleRotationChange(v: string) {
      onChange({ rotation: Number(v) as 0 | 90 | 180 | 270 });
    }

    function handleNameBlur() {
      if (selectedRack == null) return;
      commitName(nameLocal);
    }

    function handleNameKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
      if (e.key === "Enter" && selectedRack != null) {
        e.preventDefault();
        commitName(nameLocal);
      }
    }

    function handleDelete() {
      onChange(null);
    }

    const title =
      selectedCell == null
        ? t("rackEditNoCell")
        : t(hasAnyRack ? "rackEditCell" : "rackEditAddCell", { x: String(selectedCell[0] + 1), y: String(selectedCell[1] + 1) });  // counted from 1, as under the grid
    // In gate mode, delete is per-cell — removes both entrance and exit. Otherwise single-rack.
    const showDelete = hasAnyRack;

    return (
      <Card data-testid="rack-edit-panel" className="p-4">
        <div className="flex items-start justify-between">
          <span className="font-heading text-sm font-medium">{title}</span>
          {showDelete && (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDelete}
              data-testid="rack-delete-button"
              aria-label={t("rackEditRemove")}
              className="text-destructive hover:bg-destructive/10"
            >
              <Trash2 className="size-4" />
            </Button>
          )}
        </div>

        {!cellSelected && (
          <p className="text-sm text-muted-foreground">{t("rackEditClickCell")}</p>
        )}
        {cellSelected && !hasAnyRack && (
          <p className="text-sm text-muted-foreground">{t("rackEditChooseType")}</p>
        )}

        {hasAnyRack && onMove && <div className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">{t("rackEditMoveOne")}</span>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label={t("rackEditMoveSelected")}>
            {([
              ["left", "rackEditMoveLeft", -1, 0, ArrowLeft], ["up", "rackEditMoveUp", 0, -1, ArrowUp],
              ["down", "rackEditMoveDown", 0, 1, ArrowDown], ["right", "rackEditMoveRight", 1, 0, ArrowRight],
            ] as const).map(([direction, label, dx, dy, Icon]) => <Button key={direction} type="button" variant="outline" size="icon-sm"
              disabled={placing} aria-label={t(label)} onClick={() => onMove([dx, dy])}><Icon className="size-4" /></Button>)}
            {onPlacementChange && <Button type="button" variant={placing ? "secondary" : "outline"} size="sm"
              onClick={() => onPlacementChange(!placing)}>{placing ? t("rackEditCancelPlacement") : t("rackEditMoveToCell")}</Button>}
          </div>
          {placing && <p role="status" className="text-xs text-primary">{t("rackEditPlacingHint")}</p>}
          {gateConfig === "both" && kind === "gate" && <p className="text-xs text-muted-foreground">{t("rackEditGateTogether")}</p>}
        </div>}

        <div
          className={
            !cellSelected
              ? "pointer-events-none flex flex-col gap-4 opacity-50"
              : "flex flex-col gap-4"
          }
        >
          {/* Type radio group — Rack / Counter / Entrance·Exit */}
          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-muted-foreground">{t("rackEditType")}</span>
            <RadioGroup
              value={kind ?? ""}
              onValueChange={(v) => handleKindChange(v as UiKind)}
              className="flex flex-wrap gap-x-4 gap-y-2"
              data-testid="rack-type-radio"
              aria-label={t("rackEditRackType")}
              disabled={!cellSelected}
            >
              {(
                [
                  { key: "rack", label: "rackColRack" },
                  { key: "counter", label: "rackEditCounter" },
                  { key: "table", label: "rackEditTable" },
                  { key: "gate", label: "rackEditGate" },
                ] as const
              ).map(({ key, label }) => (
                <label
                  key={key}
                  className="flex cursor-pointer items-center gap-2 text-sm"
                >
                  <RadioGroupItem
                    value={key}
                    data-testid={`rack-type-${key}`}
                    disabled={!cellSelected}
                  />
                  <span>{t(label)}</span>
                </label>
              ))}
            </RadioGroup>
          </div>

          {showGateConfig && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">{t("rackEditGateLabel")}</span>
              <Select
                value={gateConfig}
                onValueChange={(v) => onGateConfigChange(v as GateConfig)}
              >
                <SelectTrigger
                  className="w-full"
                  data-testid="gate-config-trigger"
                  aria-label={t("rackEditGateConfig")}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GATE_CONFIGS.map(({ key, label }) => (
                    <SelectItem
                      key={key}
                      value={key}
                      data-testid={`gate-config-${key}`}
                    >
                      {t(label)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {showNameAndDesign && (
            <>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="rack-name-input"
                  className="text-xs font-medium text-muted-foreground"
                >
                  {t(kind === "counter" ? "rackEditCounterName" : kind === "table" ? "rackEditTableName" : "rackEditRackName")}
                </label>
                <Input
                  id="rack-name-input"
                  value={nameLocal}
                  onChange={(e) => setNameLocal(e.target.value)}
                  onBlur={handleNameBlur}
                  onKeyDown={handleNameKeyDown}
                  placeholder={t(kind === "counter" ? "rackEditCounterPlaceholder" : "rackEditRackPlaceholder")}
                  data-testid="rack-name-input"
                />
              </div>

              {kind === "table" && selectedRack ? <p className="text-xs text-muted-foreground">{t("rackEditTableHint", { width: rackBounds(selectedRack).w, depth: rackBounds(selectedRack).d, chairs: rackDiningSeats(selectedRack) })}</p> : <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">{t("rackEditDesign")}</span>
                {kind === "rack" ? (
                  <Select
                    value={rackDesign}
                    onValueChange={(v) => handleRackDesignChange(v as RackDesignKey)}
                  >
                    <SelectTrigger
                      className="w-full"
                      data-testid="rack-design-trigger"
                      aria-label={t("rackEditDesign")}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {RACK_DESIGNS.map((d) => (
                        <SelectItem key={d.key} value={d.key}>
                          {t(d.label)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Select
                    value={counterDesign}
                    onValueChange={(v) => handleCounterDesignChange(v as CounterDesignKey)}
                  >
                    <SelectTrigger
                      className="w-full"
                      data-testid="counter-design-trigger"
                      aria-label={t("rackEditDesign")}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {COUNTER_DESIGNS.map((d) => (
                        <SelectItem key={d.key} value={d.key}>
                          {t(d.label)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>}

              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">{t("rackEditRotation")}</span>
                <Select
                  value={String(rotation)}
                  onValueChange={handleRotationChange}
                >
                  <SelectTrigger
                    className="w-full"
                    data-testid="rack-rotation-trigger"
                    aria-label={t("rackEditRotation")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROTATIONS.map((r) => (
                      <SelectItem key={r} value={String(r)}>
                        {r}°
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {selectedRack && (
                <div className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-muted-foreground">{t("rackEditPreview")}</span>
                  <RackPreview
                    type={selectedRack.type}
                    designVariant={(selectedRack.design_variant ?? "a") as "a" | "b" | "c"}
                    rotation={rotation}
                  />
                </div>
              )}
            </>
          )}
        </div>
      </Card>
    );
  },
);
