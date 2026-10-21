// Treat accents, character widths and common word separators consistently in search.
export function searchText(value: string) {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().replace(/[_\s-]+/g, " ").trim();
}
