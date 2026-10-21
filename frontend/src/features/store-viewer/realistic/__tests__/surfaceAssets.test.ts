import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const root = new URL("../../../../../public/assets/materials/", import.meta.url);
const manifest = JSON.parse(readFileSync(new URL("sources.json", root), "utf8")) as {
  files: { file: string; bytes: number; sha256: string; source: string; archive_member?: string }[];
};

it.each(["diff", "rough", "nor_gl"])("bundles the original marble %s map with its recorded checksum", suffix => {
  const file = `marble_012_${suffix}_1k.jpg`;
  const entry = manifest.files.find(entry => entry.file === file)!;
  const bytes = readFileSync(new URL(file, root));
  expect(bytes.length).toBe(entry.bytes);
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(entry.sha256);
  expect(entry.source).toBe("https://ambientcg.com/get?file=Marble012_1K-JPG.zip");
  expect(entry.archive_member).toMatch(/^Marble012_1K-JPG_.*\.jpg$/);
});
