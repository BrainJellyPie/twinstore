import { useRef } from "react";

import { Button } from "@/shared/components/ui/button";

interface SupplementalUploadProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  error?: string;
  disabled?: boolean;
}

export function SupplementalUpload({ file, onFileChange, error, disabled }: SupplementalUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">Supplemental data (Optional)</label>
      {file ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-positive">File uploaded</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => onFileChange(null)}
          >
            x
          </Button>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-6 text-center space-y-2">
          <p className="text-xs text-muted-foreground">
            Upload your data (supported formats: csv, xlsx)
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            Upload
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx"
            className="hidden"
            onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          />
        </div>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
