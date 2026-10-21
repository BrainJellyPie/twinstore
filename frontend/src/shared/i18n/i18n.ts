import { create } from "zustand";
import { LOCALES, type Locale, type MessageKey } from "./messages";

import { translate } from "./translate";
export { translate } from "./translate";

const STORAGE_KEY = "twinstore.locale";

export function resolveLocale(value: string | null | undefined): Locale | null {
  const code = value?.trim().toLowerCase().split(/[-_]/)[0];
  return LOCALES.find((item) => item.code === code)?.code ?? null;
}

export function readLocale(): Locale {
  try {
    const saved = resolveLocale(localStorage.getItem(STORAGE_KEY));
    if (saved) return saved;
  } catch { /* Browser storage can be unavailable in private mode. */ }
  if (typeof navigator !== "undefined") {
    for (const language of [...(navigator.languages ?? []), navigator.language]) {
      const locale = resolveLocale(language);
      if (locale) return locale;
    }
  }
  return "en";
}

function setDocumentLanguage(locale: Locale) {
  if (typeof document !== "undefined") document.documentElement.lang = locale;
}

const initialLocale = readLocale();
setDocumentLanguage(initialLocale);
export const useLocale = create<{ locale: Locale; setLocale: (locale: Locale) => void }>((set) => ({
  locale: initialLocale,
  setLocale: (locale) => {
    if (!LOCALES.some((item) => item.code === locale)) return;
    try { localStorage.setItem(STORAGE_KEY, locale); } catch { /* Keep the selection for this page. */ }
    setDocumentLanguage(locale);
    set({ locale });
  },
}));

export function useI18n() {
  const locale = useLocale((state) => state.locale);
  return { locale, t: (key: MessageKey, values?: Record<string, string | number>) => translate(locale, key, values) };
}
