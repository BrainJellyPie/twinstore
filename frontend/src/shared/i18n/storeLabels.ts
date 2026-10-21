import { translate } from "./translate";
import type { Locale, MessageKey } from "@/shared/i18n/messages";

const TYPES: Record<string, MessageKey> = {
  convenience: "convenience", cafe: "cafe", bakery: "bakery", supermarket: "supermarket",
  cosmetics: "cosmetics", clothing: "clothing", electronics: "electronics", pharmacy: "pharmacy",
  beauty: "cosmetics", fashion: "clothing", restaurant: "restaurant", home: "homeGoods",
  books: "booksShop", sports: "sportsShop", pets: "petsShop", hardware: "hardwareShop", flowers: "flowersShop",
  travel: "travelShop", garden: "gardenShop", baby: "babyShop", toys: "toysShop", crafts: "craftsShop",
  music: "musicShop", jewelry: "jewelryShop", eyewear: "eyewearShop", gift: "giftShop",
};

export function storeTypeLabel(type: string, locale: Locale): string {
  const key = Object.prototype.hasOwnProperty.call(TYPES, type) ? TYPES[type] : undefined;
  if (key) return translate(locale, key);
  const words = type.replace(/[_-]+/g, " ").trim();
  return words ? words[0]!.toUpperCase() + words.slice(1) : translate(locale, "store");
}
