import { expect, it } from "vitest";
import { messages } from "../messages";

type Catalog = Record<string, readonly string[]>;
const modules = import.meta.glob<Record<string, Catalog>>(["../*Messages.ts", "../messages/*.ts"], { eager: true });

it("gives each message key one owner so merged catalogs cannot silently change placeholders", () => {
  const owners = new Map<string, string>();
  for (const [path, module] of Object.entries(modules)) {
    for (const catalog of Object.values(module)) {
      for (const [key, translations] of Object.entries(catalog)) {
        expect(owners.has(key), `${key} occurs in both ${owners.get(key)} and ${path}`).toBe(false);
        owners.set(key, path);
        expect((messages as Catalog)[key], `${key} from ${path} was overridden or omitted`).toBe(translations);
      }
    }
  }
  expect(owners.size).toBeGreaterThan(0);
});
