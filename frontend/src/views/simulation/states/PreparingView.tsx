import { useEffect, useRef, useState } from "react";
import { Loader2, AlertCircle, RefreshCw, Users } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { useI18n } from "@/shared/i18n/i18n";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/shared/components/ui/alert-dialog";
import type { SetupGenerationState } from "@/shared/queries/useSetupGeneration";
import { GenerationConfirmDialog } from "./GenerationConfirmDialog";

interface Props {
  generation: SetupGenerationState;
  contextKind: "layout" | "persona";
  projectName: string;
  layouts: readonly { id: string; name: string }[];
  selectedSetupId: string;
  onLayoutSelect: (id: string) => void;
  onBackToStores: () => void;
  onAbandonProject: () => void | Promise<void>;
}

const actionClass = "h-auto min-h-10 w-full whitespace-normal sm:w-auto";
// Alert-dialog actions compose Button via a slot, so inline wrapping also overrides its base nowrap style.
const confirmationActionStyle = { whiteSpace: "normal", height: "auto", maxWidth: "100%" } as const;

export function PreparingView({ generation, contextKind, projectName, layouts, selectedSetupId, onLayoutSelect, onBackToStores, onAbandonProject }: Props) {
  const { t } = useI18n();
  const { phase, kind, error, retry, retrying, loadingStatus, errorSource, note, writing, confirm, answer, answering, answerError } = generation;
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deletingRef = useRef(false);
  const mounted = useRef(false);
  const deleteButton = useRef<HTMLButtonElement>(null);
  const backButton = useRef<HTMLButtonElement>(null);
  const deleteNotice = useRef<HTMLParagraphElement>(null);
  const deleteErrorNotice = useRef<HTMLParagraphElement>(null);
  const headingNotice = useRef<HTMLHeadingElement>(null);
  const reloadButton = useRef<HTMLButtonElement>(null);
  const focusAfterRead = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (deleteError !== null) deleteErrorNotice.current?.focus(); }, [deleteError]);

  const statusUnavailable = errorSource === "status";
  useEffect(() => {
    if (!focusAfterRead.current || loadingStatus || retrying) return;
    focusAfterRead.current = false;
    if (document.activeElement === document.body || document.activeElement === reloadButton.current) {
      (reloadButton.current ?? headingNotice.current)?.focus();
    }
  }, [statusUnavailable, loadingStatus, retrying]);
  const isGenerationFailed = phase === "failed" && !statusUnavailable && !loadingStatus;
  const isLayoutFailed = isGenerationFailed && (kind === "layout" || (kind === null && contextKind === "layout"));
  const isPersonaFailed = isGenerationFailed && !isLayoutFailed;
  // A store whose layout or customers keep failing can always be deleted and started over.
  const canDelete = isLayoutFailed || isPersonaFailed;
  useEffect(() => { if (!canDelete) setConfirmOpen(false); }, [canDelete]);
  const canGenerate = phase === "idle" && contextKind === "persona" && !loadingStatus;
  const failed = isLayoutFailed || isPersonaFailed || (statusUnavailable && !loadingStatus);
  const heading = loadingStatus ? t("checkingGenerationStatus") : statusUnavailable ? t("generationStatusUnavailable")
    : isLayoutFailed ? t("layoutAnalysisFailed") : isPersonaFailed ? t("personaGenerationFailed")
    : canGenerate ? t("personasNotGenerated") : phase === "layout" ? t("analyzingLayout")
    : phase === "persona" ? t("generatingPersonas") : contextKind === "layout" ? t("preparingLayoutAnalysis") : t("preparingPersonaGeneration");

  const confirmDelete = async () => {
    if (deletingRef.current) return;
    deletingRef.current = true;
    setConfirmOpen(false); setDeleting(true); setDeleteError(null);
    try { await onAbandonProject(); }
    catch (cause) { if (mounted.current) setDeleteError(cause instanceof Error ? cause.message : typeof cause === "string" ? cause : ""); }
    finally { deletingRef.current = false; if (mounted.current) setDeleting(false); }
  };

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto p-4 sm:p-8">
      <div className="m-auto w-full min-w-0 max-w-lg space-y-4 rounded-2xl border bg-card p-5 [overflow-wrap:anywhere] sm:p-6">
        {layouts.length > 1 && <label className="block space-y-1 text-sm font-medium">
          <span>{t("switchPreparingLayout")}</span>
          <select aria-label={t("switchPreparingLayout")} className="block w-full min-w-0 rounded-lg border bg-background px-3 py-2 text-sm" value={selectedSetupId} disabled={deleting}
            onChange={(event) => { const id = event.target.value; if (id !== selectedSetupId && layouts.some(layout => layout.id === id)) onLayoutSelect(id); }}>
            {layouts.map((layout, index) => <option key={layout.id} value={layout.id}>{layout.name.trim() ? layout.name : t("unnamedLayout", { number: index + 1 })}</option>)}
          </select>
        </label>}
        <div className="space-y-3 text-center">
          {deleting ? <Loader2 className="mx-auto size-8 animate-spin text-muted-foreground" aria-hidden />
            : failed ? <AlertCircle className="mx-auto size-8 text-destructive" aria-hidden />
            : canGenerate ? <Users className="mx-auto size-8 text-muted-foreground" aria-hidden />
            : <Loader2 className="mx-auto size-8 animate-spin text-muted-foreground" aria-hidden />}
          <h2 ref={headingNotice} tabIndex={-1} className={failed && !deleting ? "text-lg font-semibold text-destructive outline-none" : "text-lg font-semibold outline-none"}>{deleting ? t("deletingStore") : heading}</h2>
          {deleting && <p ref={deleteNotice} role="status" aria-label={t("deletingStore")} tabIndex={-1} className="text-sm text-muted-foreground outline-none">{t("generationContinueHint")}</p>}
          {!deleting && failed && <p role="alert" className="text-sm text-muted-foreground">{error || t(statusUnavailable ? "generationStatusUnavailable" : isLayoutFailed ? "layoutErrorFallback" : "personaErrorFallback")}</p>}
          {!deleting && isLayoutFailed && <p className="text-sm text-muted-foreground">{t("layoutFailureHint")}</p>}
          {!deleting && (isPersonaFailed || canGenerate) && <p className="text-sm text-muted-foreground">{t("generatePersonasHint")}</p>}
          {!deleting && (statusUnavailable || loadingStatus) && <p role={loadingStatus ? "status" : undefined} className="text-sm text-muted-foreground">{t("generationStatusReadHint")}</p>}
          {!deleting && !failed && !canGenerate && !statusUnavailable && !loadingStatus && note && <div role="status" className="space-y-1 rounded-lg border p-3 text-sm">
            <p>{t("generationWaitsForLocalModel")}</p><p className="text-xs text-muted-foreground">{note}</p>
          </div>}
          {!deleting && !failed && !canGenerate && !statusUnavailable && !loadingStatus && writing && <p role="status" className="text-sm font-medium tabular-nums">
            {t("writingCustomers", { written: writing.written, total: writing.total })}
          </p>}
          {!deleting && !failed && !canGenerate && !statusUnavailable && !loadingStatus && <p role="status" className="text-sm text-muted-foreground">{t("generationContinueHint")}</p>}
          {deleteError !== null && <p ref={deleteErrorNotice} role="alert" tabIndex={-1} className="space-y-1 rounded-lg border border-destructive/30 p-3 text-sm text-destructive outline-none">
            <span className="block">{t("deleteStoreFailed")}</span>{deleteError && <span className="block text-xs">{deleteError}</span>}
          </p>}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-center">
          {!deleting && statusUnavailable && <Button ref={reloadButton} className={actionClass} onClick={(event) => {
            if (!retrying && !loadingStatus) { focusAfterRead.current = document.activeElement === event.currentTarget; retry(); }
          }} disabled={retrying || loadingStatus}>
            <RefreshCw className={retrying ? "size-4 shrink-0 animate-spin" : "size-4 shrink-0"} aria-hidden />
            {retrying ? t("checkingGenerationStatus") : t("reloadGenerationStatus")}
          </Button>}
          {!deleting && (isPersonaFailed || canGenerate) && <Button className={actionClass} onClick={() => { if (!retrying) retry(); }} disabled={retrying}>
            <RefreshCw className={retrying ? "size-4 shrink-0 animate-spin" : "size-4 shrink-0"} aria-hidden />
            {retrying ? t("tryingAgain") : canGenerate ? t("generate") : t("tryAgain")}
          </Button>}
          <Button ref={backButton} variant="outline" className={actionClass} onClick={onBackToStores}>{t("backToStores")}</Button>
          {!deleting && canDelete && <Button ref={deleteButton} variant="destructive" className={actionClass}
            onClick={() => { setDeleteError(null); setConfirmOpen(true); }}>{t("deleteStoreAndStartOver")}</Button>}
        </div>
      </div>
      {canDelete && <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent className="max-h-[92dvh] grid-cols-1 overflow-y-auto [overflow-wrap:anywhere] data-[size=default]:max-w-[calc(100%-2rem)] data-[size=default]:sm:max-w-lg"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            if (deleteError !== null) deleteErrorNotice.current?.focus();
            else if (deletingRef.current) deleteNotice.current?.focus();
            else (deleteButton.current ?? backButton.current)?.focus();
          }}>
          <AlertDialogHeader className="min-w-0">
            <AlertDialogTitle>{t("deleteStoreTitle")}</AlertDialogTitle>
            <AlertDialogDescription>{t("deleteStoreDescription", { name: projectName.trim() || t("untitledStore") })}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="min-w-0">
            <AlertDialogCancel className={actionClass} style={confirmationActionStyle}>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" className={actionClass} style={confirmationActionStyle} onClick={() => { void confirmDelete(); }}>{t("deleteStoreAndStartOver")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>}
      {confirm && answer && !failed && !deleting && (
        <GenerationConfirmDialog confirm={confirm} answering={answering ?? false} error={answerError ?? null} onAnswer={answer} />
      )}
    </div>
  );
}
