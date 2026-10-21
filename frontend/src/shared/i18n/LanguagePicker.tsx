import { Languages } from "lucide-react";
import { resolveLocale, useI18n, useLocale } from "./i18n";
import { LOCALES } from "./messages";

export function LanguagePicker() {
  const { locale, t } = useI18n();
  const setLocale = useLocale((state) => state.setLocale);
  return (
    <div className="glass relative flex h-9 w-9 shrink-0 items-center justify-center gap-1.5 rounded-xl focus-within:ring-2 focus-within:ring-ring sm:w-auto sm:px-2.5" title={LOCALES.find((item) => item.code === locale)?.label}>
      <Languages className="size-4" aria-hidden />
      <span className="hidden text-xs uppercase sm:inline" aria-hidden>{locale}</span>
      <select name="language" value={locale} aria-label={t("language")} className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        onChange={(event) => { const next = resolveLocale(event.target.value); if (next) setLocale(next); }}>
        {LOCALES.map((item) => <option key={item.code} value={item.code} lang={item.code}>{item.label}</option>)}
      </select>
    </div>
  );
}
