import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import * as api from "@/shared/api/client";
import { queryKeys } from "@/shared/queries/keys";
import {
  captureBatchPreview,
  captureBatchSave,
} from "@/services/mutations/captureBatch";
import { useSimulationStore } from "@/stores/simulationStore";
import { FloorPlanPreview } from "@/features/layouts/components/FloorPlanPreview";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import type { MessageKey } from "@/shared/i18n/messages";

const STATUS: Record<string, MessageKey> = { completed: "capStatusCompleted", failed: "capStatusFailed", pending: "capStatusPending", running: "capStatusRunning" };

export function CaptureBatch({
  projectId,
  captures,
  onReview,
}: {
  projectId: string;
  captures: api.CaptureStatus[];
  onReview: (id: string) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [setupId, setSetupId] = useState("");
  const [requestId, setRequestId] = useState("");
  const [acceptReduced, setAcceptReduced] = useState(false);
  const preview = useMutation(captureBatchPreview(projectId));
  const save = useMutation(captureBatchSave(projectId));
  const qc = useQueryClient();
  const navigate = useNavigate();
  const layouts = useQuery({
    queryKey: queryKeys.setups(projectId),
    queryFn: ({ signal }) => api.getSetups(projectId, signal),
    enabled: open,
  });
  const setups = layouts.data ?? [];
  const base = setupId || setups[0]?.id || "";
  const busy = preview.isPending || save.isPending;
  const chosen = selected.filter((id) =>
    captures.some(
      (c) => c.capture_id === id && c.status === "completed" && c.items > 0,
    ),
  );
  const valid =
    chosen.length > 0 &&
    chosen.length <= 20 &&
    chosen.length === selected.length &&
    setups.some((s) => s.id === base) &&
    !layouts.isError;
  const report = preview.data;
  const sameSelection =
    preview.variables?.setup_id === base &&
    JSON.stringify(preview.variables?.capture_ids) === JSON.stringify(chosen);
  const clear = () => {
    preview.reset();
    save.reset();
    setRequestId("");
    setAcceptReduced(false);
  };
  return (
    <section
      className="max-h-[60dvh] shrink-0 overflow-y-auto rounded-2xl border bg-card p-3 text-sm"
      aria-label={t("capBatchAria")}
    >
      <Button
        variant="outline"
        disabled={busy}
        onClick={() => {
          setOpen(!open);
          if (!open) clear();
        }}
      >
        {t("capBatchToggle")}
      </Button>
      {open && (
        <div className="mt-3 space-y-3">
          <p>{t("capBatchIntro")}</p>
          <label className="block">
            {t("capBaseLayout")}
            <select
              className="mt-1 block h-10 w-full rounded-lg border bg-background px-2"
              disabled={busy || layouts.isPending}
              value={base}
              onChange={(e) => {
                clear();
                setSetupId(e.target.value);
              }}
            >
              {!base && <option value="">{t("capChooseLayout")}</option>}
              {setups.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name || s.id}
                </option>
              ))}
            </select>
          </label>
          {layouts.isError && (
            <div role="alert">
              {t("capLayoutsError")}{" "}
              <Button variant="outline" onClick={() => void layouts.refetch()}>
                {t("capRetryLayouts")}
              </Button>
            </div>
          )}
          {!layouts.isPending && !layouts.isError && !setups.length && (
            <p>{t("capNoLayouts")}</p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => {
                clear();
                setSelected(
                  captures
                    .filter((c) => c.status === "completed" && c.items > 0)
                    .slice(0, 20)
                    .map((c) => c.capture_id),
                );
              }}
            >
              {t("capSelectFirst20")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => {
                clear();
                setSelected([]);
              }}
            >
              {t("capClearSelection")}
            </Button>
          </div>
          <p>{t("capSelectedCount", { count: chosen.length })}</p>
          <div className="grid max-h-64 gap-2 overflow-auto sm:grid-cols-2">
            {captures.map((c) => {
              const ready = c.status === "completed" && c.items > 0;
              const checked = selected.includes(c.capture_id);
              return (
                <div
                  key={c.capture_id}
                  className="flex items-center gap-2 rounded-lg border p-2"
                >
                  <label className="flex min-w-0 flex-1 items-center gap-2">
                    <input
                      type="checkbox"
                      disabled={
                        busy || !ready || (!checked && chosen.length >= 20)
                      }
                      checked={checked}
                      onChange={() => {
                        clear();
                        setSelected(
                          checked
                            ? selected.filter((id) => id !== c.capture_id)
                            : [...selected, c.capture_id],
                        );
                      }}
                    />
                    <img
                      className="h-12 w-16 rounded object-cover"
                      src={api.captureImageUrl(projectId, c.capture_id)}
                      alt=""
                    />
                    <span className="min-w-0 break-words">
                      {c.image_name}
                      <br />
                      <span className="text-xs text-muted-foreground">
                        {t("capBatchItemMeta", { status: STATUS[c.status] ? t(STATUS[c.status]!) : c.status, count: c.items, currency: c.options.currency })}
                      </span>
                    </span>
                  </label>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      clear();
                      setOpen(false);
                      onReview(c.capture_id);
                    }}
                  >
                    {t("capReview")}
                  </Button>
                </div>
              );
            })}
          </div>
          {chosen.length !== selected.length && (
            <p role="alert">{t("capSelectionStale")}</p>
          )}
          <Button
            disabled={!valid || busy}
            onClick={() => {
              clear();
              setSetupId(base);
              preview.mutate(
                { capture_ids: chosen, setup_id: base },
                {
                  onSuccess: () =>
                    setRequestId(crypto.randomUUID().replace(/-/g, "")),
                },
              );
            }}
          >
            {t("capPreviewCombined")}
          </Button>
          {busy && (
            <p role="status">
              {save.isPending
                ? t("capSavingCombined")
                : t("capCheckingPlacement")}
            </p>
          )}
          {(preview.error || save.error) && (
            <p role="alert" className="text-destructive">
              {preview.error?.message || save.error?.message}
            </p>
          )}
          {report && sameSelection && (
            <div className="space-y-3">
              <p>
                {t("capBatchSummary", { racks: report.rack_ids.length, items: report.placed_items, facings: report.placed_facings })}
              </p>
              <p>
                {t("capBatchCaveat", { estimated: report.estimated_prices, unrecognized: report.unrecognized_items })}
              </p>
              <FloorPlanPreview store={report.store} areas={[]} />
              <p className="break-words text-xs">
                {t("capNewRackIds", { ids: report.rack_ids.join(", ") })}
              </p>
              {report.notes.map((note, i) => (
                <p key={i} className="text-xs">
                  {note}
                </p>
              ))}
              {!!report.dropped.length && (
                <p role="alert">{t("capDropped", { products: report.dropped.join(", ") })}</p>
              )}
              {report.reduced_facings > 0 && (
                <label className="block rounded-lg border p-2">
                  <input
                    type="checkbox"
                    checked={acceptReduced}
                    disabled={busy || !!save.variables}
                    onChange={(e) => setAcceptReduced(e.target.checked)}
                  />{" "}
                  {t("capAcceptReduced", { placed: report.placed_facings, requested: report.requested_facings, reduced: report.reduced_facings })}
                </label>
              )}
              {!save.data && (
                <Button
                  disabled={
                    !valid ||
                    busy ||
                    !requestId ||
                    report.dropped.length > 0 ||
                    (report.reduced_facings > 0 && !acceptReduced)
                  }
                  onClick={() =>
                    save.mutate(
                      {
                        capture_ids: chosen,
                        setup_id: base,
                        source_sha256: report.source_sha256,
                        request_id: requestId,
                        allow_reduced_facings: acceptReduced,
                      },
                      {
                        onSuccess: () => {
                          void qc.invalidateQueries({
                            queryKey: queryKeys.project(projectId),
                          });
                        },
                      },
                    )
                  }
                >
                  {save.error
                    ? t("capRetrySaveDraft")
                    : t("capSaveCombined")}
                </Button>
              )}
            </div>
          )}
          {save.data && (
            <div role="status">
              <p>{t("capCombinedSaved")}</p>
              <Button
                onClick={() => {
                  if (save.data) {
                    useSimulationStore
                      .getState()
                      .setSelectedSetupId(save.data.setup_id);
                    void navigate({
                      to: "/projects/$pid",
                      params: { pid: projectId },
                    });
                  }
                }}
              >
                {t("capOpenCombined")}
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
