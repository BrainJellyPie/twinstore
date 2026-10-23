// Backend takes one file per SKU — multi-SKU upload fans out into N requests.

import { BASE } from "./client";

export interface UploadedSkuImage {
  sku: string;
  url: string;
}

// Narrowed to formats accepted by backend `images.py::_ALLOWED_FORMATS`;
// prevents callers from sending e.g. GIF under a png MIME and getting a 422.
export type UploadableImageExtension = "png" | "jpeg" | "webp";

async function uploadOne(
  projectId: string,
  sku: string,
  bytes: Uint8Array,
  extension: UploadableImageExtension,
): Promise<UploadedSkuImage> {
  const mime =
    extension === "jpeg" ? "image/jpeg"
    : extension === "webp" ? "image/webp"
    : "image/png";
  const blob = new Blob([bytes as BlobPart], { type: mime });
  const form = new FormData();
  form.append("file", blob, `${sku}.${extension}`);

  const res = await fetch(
    `${BASE}/api/projects/${encodeURIComponent(projectId)}/sku-images?sku=${encodeURIComponent(sku)}`,
    { method: "POST", body: form },
  );
  if (!res.ok) {
    const raw = await res.text().catch(() => "");
    const text = raw.slice(0, 200) || res.statusText;
    throw new Error(`SKU image upload failed (${sku}): ${text}`);
  }
  return (await res.json()) as UploadedSkuImage;
}

// Backend serializes `image_url` as an origin-less path (e.g.
// "/api/projects/p1/images?sku=tea&v=abc"). In dev the frontend (5173) and backend
// (8000) origins differ, so we must prefix BASE; in prod BASE is "" and this is
// a no-op.
export function resolveImageUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  if (/^https?:\/\//.test(url)) return url;  // already absolute
  return `${BASE}${url}`;
}

export async function uploadSkuImages(
  projectId: string,
  skuToBytes: Record<string, { bytes: Uint8Array; extension: UploadableImageExtension }>,
): Promise<UploadedSkuImage[]> {
  const entries = Object.entries(skuToBytes);
  if (entries.length === 0) return [];
  // A failed upload must not release the workbook's busy state while older image writes are still running.
  const settled = await Promise.allSettled(
    entries.map(([sku, { bytes, extension }]) =>
      uploadOne(projectId, sku, bytes, extension),
    ),
  );
  const failed = settled.find((result) => result.status === "rejected");
  if (failed?.status === "rejected") {
    const reason: unknown = failed.reason;
    throw reason instanceof Error ? reason : new Error(String(reason));
  }
  return settled.flatMap((result) => result.status === "fulfilled" ? [result.value] : []);
}
