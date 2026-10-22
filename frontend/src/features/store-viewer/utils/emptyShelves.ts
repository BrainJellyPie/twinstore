import type { EmptySpell } from "@/shared/api/client";

/** The products gone from each rack at a moment of a day (clock seconds). */
export function emptyAt(spells: EmptySpell[], day: number, second: number): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const spell of spells) {
    if (spell.day !== day || spell.start > second || spell.end <= second) continue;
    const names = out.get(spell.rack_id) ?? [];
    const name = spell.name || spell.sku;
    if (!names.includes(name)) names.push(name);
    out.set(spell.rack_id, names);
  }
  return out;
}
