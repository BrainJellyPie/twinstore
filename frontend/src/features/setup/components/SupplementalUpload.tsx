import { useEffect, useRef } from "react";
import { useI18n } from "@/shared/i18n/i18n";
import { Button } from "@/shared/components/ui/button";

interface SupplementalUploadProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  error?: string;
  disabled?: boolean;
}

export function SupplementalUpload({ file, onFileChange, error, disabled }: SupplementalUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const chooseRef = useRef<HTMLButtonElement>(null);
  const previousFile = useRef(file);
  useEffect(() => {
    const removed = previousFile.current !== null && file === null;
    previousFile.current = file;
    if (removed) chooseRef.current?.focus();
  }, [file]);
  const { locale, t } = useI18n();
  const unit = file && file.size >= 1024 * 1024 ? "megabyte" : file && file.size >= 1024 ? "kilobyte" : "byte";
  const divisor = unit === "megabyte" ? 1024 * 1024 : unit === "kilobyte" ? 1024 : 1;
  const fileSize = file ? new Intl.NumberFormat(locale, { style: "unit", unit, maximumFractionDigits: 1 }).format(file.size / divisor) : "";

  return (
    <div className="space-y-1.5">
      <label htmlFor="setup-supplemental-file" className="text-sm font-medium">{t("supplementalData")}</label>
      <p className="text-xs text-muted-foreground">{t("supplementalHint")}</p>
      {file ? (
        <div className="flex min-w-0 items-start gap-2 rounded-lg border p-3">
          <div className="min-w-0 flex-1">
            <span role="status" className="text-xs text-positive">{t("fileSelected")}</span>
            <span className="block break-all text-sm">{file.name}</span>
            <span className="text-xs text-muted-foreground">{fileSize}</span>
          </div>
          <Button id="setup-supplemental-remove" type="button" variant="outline" size="sm" disabled={disabled}
            aria-label={t("removeSelectedFile")} onClick={() => onFileChange(null)}>{t("remove")}</Button>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-6 text-center">
          <Button ref={chooseRef} id="setup-supplemental-choose" type="button" variant="outline" size="sm" disabled={disabled}
            onClick={() => inputRef.current?.click()}>{t("chooseFile")}</Button>
        </div>
      )}
      <input id="setup-supplemental-file" ref={inputRef} type="file" accept=".csv,.xlsx" className="hidden" disabled={disabled}
        aria-invalid={!!error} aria-describedby={error ? "setup-supplemental-error" : undefined}
        onChange={(event) => { onFileChange(event.target.files?.[0] ?? null); event.target.value = ""; }} />
      {error && <p id="setup-supplemental-error" role="alert" className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
