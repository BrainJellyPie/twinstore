import { LOCALES, messages, type Locale, type MessageKey } from "./messages";

export function translate(locale: Locale, key: MessageKey, values: Record<string, string | number> = {}): string {
  const index = LOCALES.findIndex((item) => item.code === locale);
  const template = messages[key][index] ?? messages[key][0];
  return template.replace(/\{(\w+)\}/g, (placeholder: string, name: string) => {
    const value = values[name];
    return value === undefined ? placeholder : typeof value === "number" ? new Intl.NumberFormat(locale).format(value) : value;
  });
}
