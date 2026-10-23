import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2, Download, Upload } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { useReplaceSlots } from "@/shared/mutations/useReplaceSlots";
import { getBlockedFaces } from "@/shared/api/client";
import { buildLayoutWorkbook } from "@/features/layouts/excel/buildLayoutWorkbook";
import { parseLayoutWorkbook } from "@/features/layouts/excel/parseLayoutWorkbook";
import { extractSkuImages } from "@/features/layouts/excel/extractSkuImages";
import { uploadSkuImages } from "@/shared/api/images";
import type { Store } from "@/shared/types/domain";
import { useI18n } from "@/shared/i18n/i18n";

interface LayoutExcelControlsProps {
  store: Store;
  projectId: string;
  setupId: string;
  /** "full" (default) = download + upload, "download" = download only. Settings tab uses "download". */
  mode?: "full" | "download";
}

export function LayoutExcelControls(props: LayoutExcelControlsProps) {
  return <ExcelControls key={`${props.projectId}:${props.setupId}`} {...props} />;
}

function ExcelControls({
  store,
  projectId,
  setupId,
  mode = "full",
}: LayoutExcelControlsProps) {
  const { t } = useI18n();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [uploadInfo, setUploadInfo] = useState<{ count: number; clearedCount: number; imageWarning?: string } | null>(null);
  const [uploadParseError, setUploadParseError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const uploadInFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const replace = useReplaceSlots();

  // Gate the "File uploaded" feedback on the live store: when the store no
  // longer has any placed items (e.g. floor force-edit cleared them all), the
  // recorded upload result is stale and the message should disappear.
  const currentItemCount = store.racks.reduce(
    (n, r) => n + r.slots.reduce((m, s) => m + s.items.length, 0),
    0,
  );

  const handleDownload = useCallback(async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      const blocked = await getBlockedFaces(store);
      const buffer = await buildLayoutWorkbook({ store, blocked });
      const blob = new Blob([buffer], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${store.name || "store"}_layout_template.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : String(e));
    } finally {
      setDownloading(false);
    }
  }, [store]);

  const handleFile = useCallback(async (file: File) => {
    if (uploadInFlight.current) return;
    uploadInFlight.current = true;
    setUploading(true);
    setUploadInfo(null);
    setUploadParseError(null);
    replace.reset();
    try {
      const buffer = await file.arrayBuffer();
      if (!mounted.current) return;
      const { slots } = parseLayoutWorkbook(buffer);

      // Extract embedded SKU images and upload. Images are side data — if this fails,
      // continue with the slots replace (image upload is best-effort).
      const skuImages = await extractSkuImages(buffer);
      if (!mounted.current) return;
      let imageWarning: string | null = null;
      if (Object.keys(skuImages).length > 0) {
        try {
          const uploaded = await uploadSkuImages(projectId, skuImages);
          const replacements = new Map(uploaded.map((image) => [image.sku, image.url]));
          for (const slot of slots) {
            const url = replacements.get(slot.sku);
            if (url !== undefined) slot.image_url = url;
          }
        } catch (err) {
          imageWarning = err instanceof Error ? err.message : String(err);
        }
      }

      if (!mounted.current) return;
      const res = await replace.mutateAsync({ projectId, setupId, slots });
      if (!mounted.current) return;
      // backend returns res.count = sum(len(slot.items)), i.e. placement count.
      // Aggregate `cleared` the same way — by SKU placement, not by coordinate.
      const clearedCount = res.cleared.reduce(
        (n, c) => n + c.cleared_skus.length,
        0,
      );
      setUploadInfo({
        count: res.count,
        clearedCount,
        ...(imageWarning ? { imageWarning } : {}),
      });
    } catch (e) {
      // Failures before the mutation runs (e.g. missing rack_layout sheet,
      // corrupt xlsx). Backend mutation failures surface via `replace.error`.
      if (mounted.current) setUploadParseError(e instanceof Error ? e.message : String(e));
    } finally {
      uploadInFlight.current = false;
      if (mounted.current) setUploading(false);
    }
  }, [projectId, setupId, replace]);

  const uploadError =
    uploadParseError ?? (replace.error instanceof Error ? replace.error.message : null);

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex gap-1.5">
        {mode === "full" && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 flex-1 text-xs"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || replace.isPending}
          >
            {uploading || replace.isPending ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Upload className="mr-1 size-3" />}
            {t("excelUpload")}
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 flex-1 text-xs"
          onClick={() => void handleDownload()}
          disabled={downloading}
        >
          {downloading ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Download className="mr-1 size-3" />}
          {t("excelDownload")}
        </Button>
      </div>
      {mode === "full" && (
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx"
          disabled={uploading || replace.isPending}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
            e.target.value = "";
          }}
        />
      )}
      {mode === "full" && uploadInfo && currentItemCount > 0 && (
        <>
          <p className="text-xs text-muted-foreground">
            {uploadInfo.clearedCount > 0
              ? t("excelUploadedCleared", { count: uploadInfo.count, cleared: uploadInfo.clearedCount })
              : t("excelUploaded", { count: uploadInfo.count })}
          </p>
          {uploadInfo.imageWarning && (
            <p className="text-xs text-warn">{uploadInfo.imageWarning}</p>
          )}
        </>
      )}
      {mode === "full" && uploadError && (
        <p className="flex items-start gap-1 text-xs text-destructive">
          <AlertCircle className="mt-0.5 size-3 shrink-0" />
          <span>{uploadError}</span>
        </p>
      )}
      {downloadError && (
        <p className="flex items-start gap-1 text-xs text-destructive">
          <AlertCircle className="mt-0.5 size-3 shrink-0" />
          <span>{downloadError}</span>
        </p>
      )}
    </div>
  );
}
