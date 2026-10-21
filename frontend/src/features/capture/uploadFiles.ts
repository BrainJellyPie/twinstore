export const MAX_QUEUE_FILES = 20;
export const MAX_FILE_BYTES = 25 * 1024 * 1024;
export const MAX_QUEUE_BYTES = 100 * 1024 * 1024;
export function fileProblem(file: File): string | null {
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_FILE_BYTES) return "The file exceeds 25 MB.";
  if (
    !(
      ["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      (!file.type && /\.(jpe?g|png|webp)$/i.test(file.name))
    )
  )
    return "Choose a JPEG, PNG or WebP image.";
  return null;
}
export async function fileDigest(file: File): Promise<string> {
  if (!globalThis.crypto?.subtle || !globalThis.crypto.randomUUID)
    throw new Error(
      "Photo queue needs HTTPS or localhost for duplicate checking and safe retries.",
    );
  const data = await new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(new Error("Could not read this file. Choose it again."));
    reader.onload = () =>
      reader.result instanceof ArrayBuffer
        ? resolve(reader.result)
        : reject(new Error("Could not read this file."));
    reader.readAsArrayBuffer(file);
  });
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}
