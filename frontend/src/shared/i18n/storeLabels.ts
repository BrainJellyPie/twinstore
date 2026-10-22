import { translate } from "./translate";
import { messages, type Locale, type MessageKey } from "@/shared/i18n/messages";

const TYPES: Record<string, MessageKey> = {
  convenience: "convenience", cafe: "cafe", bakery: "bakery", supermarket: "supermarket",
  cosmetics: "cosmetics", clothing: "clothing", electronics: "electronics", pharmacy: "pharmacy",
  beauty: "cosmetics", fashion: "clothing", restaurant: "restaurant", home: "homeGoods",
  books: "booksShop", sports: "sportsShop", pets: "petsShop", hardware: "hardwareShop", flowers: "flowersShop",
  travel: "travelShop", garden: "gardenShop", baby: "babyShop", toys: "toysShop", crafts: "craftsShop",
  music: "musicShop", jewelry: "jewelryShop", eyewear: "eyewearShop", gift: "giftShop",
};

const fold = (text: string) => text.normalize("NFD").replace(/\p{M}/gu, "").trim().toLowerCase();

// Stores made before category ids (the sample store among them) carry the English label, e.g. "Convenience store".
const BY_ENGLISH_LABEL = new Map(Object.values(TYPES).map((key) => [fold(translate("en", key)), key]));

export function storeTypeLabel(type: string, locale: Locale): string {
  const key = Object.prototype.hasOwnProperty.call(TYPES, type) ? TYPES[type] : BY_ENGLISH_LABEL.get(fold(type));
  if (key) return translate(locale, key);
  const words = type.replace(/[_-]+/g, " ").trim();
  return words ? words[0]!.toUpperCase() + words.slice(1) : translate(locale, "store");
}

/** Display name of a store format (template); the id stays the API value and unknown formats keep the server's name. */
export function templateName(id: string, name: string, locale: Locale): string {
  const key = `tpl_${id}`;
  return Object.prototype.hasOwnProperty.call(messages, key) ? translate(locale, key as MessageKey) : name;
}
