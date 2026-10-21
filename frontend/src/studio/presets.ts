// Shelf studio assortments, bottom shelf first. Names are generic (no real brands); the package
// shape, size and colours come from Realistic mode's product catalog, so they look like the twin.

export interface Run {
  name: string;
  facings: number;
  price: number;
  promo?: string;
  // an empty stretch of this many facings instead of a product
  gap?: number;
}

export interface Preset {
  header: string;
  levels: Run[][];
  // the bays left and right of the centre one (partly in frame)
  neighbours: [Run[][], Run[][]];
}

const run = (name: string, facings: number, price: number, promo?: string): Run => ({ name, facings, price, promo });
const gap = (facings: number): Run => ({ name: "", facings: 0, price: 0, gap: facings });

const DRINKS: Run[][] = [
  [run("Fizzo Cola 2 Liter", 4, 2.79), run("Spritz Lemon-Lime Soda 2 Liter", 3, 2.69), run("Sunny Orange Soda 2 Liter", 3, 2.69)],
  [run("Sunny Orange Soda 12oz can", 5, 1.29), run("Purple Grape Soda 12oz can", 4, 1.29), gap(2), run("Volt Energy Drink 16oz can", 5, 2.99)],
  [run("Fizzo Zero Cola 20oz", 5, 2.29), run("Fizzo Cola 20oz", 5, 2.29), run("Spritz Lemon-Lime Soda 20oz", 4, 2.19)],
  [run("Leafy Green Tea 16.9oz", 5, 1.89, "1+1"), run("Leafy Lemon Iced Tea 16.9oz", 5, 1.99), run("Leafy Peach Iced Tea 16.9oz", 5, 1.99)],
  [run("Clara Sparkling Water 1 Liter", 6, 1.69), run("Clara Lime Sparkling Water 1 Liter", 6, 1.79)],
];

const JUICE: Run[][] = [
  [run("Grove Orange Juice 2 Liter", 5, 4.49), run("Grove Apple Juice 2 Liter", 5, 4.29)],
  [run("Peak Sports Drink 28oz", 6, 2.49), run("Peak Blue Sports Drink 28oz", 6, 2.49)],
  [run("Brewline Cold Brew Coffee 12oz", 6, 3.29), run("Brewline Mocha Coffee Drink 12oz", 6, 3.29)],
  [run("Clara Spring Water 16.9oz", 8, 1.19), run("Clara Spring Water 1 Liter", 6, 1.59)],
  [run("Fizzo Cherry Cola 20oz", 6, 2.29), run("Spritz Ginger Ale Soda 20oz", 6, 2.19)],
];

const SNACKS: Run[][] = [
  [run("Crunchy Sea Salt Chips 8oz", 4, 4.29), run("Crunchy BBQ Chips 8oz", 4, 4.29)],
  [run("Corn Twists Cheese Puffs 8oz", 4, 3.99), run("Tortilla Nacho Chips 9oz", 4, 4.49)],
  [run("Golden Pretzel Twists 10oz", 4, 3.49), run("Crispy Cheese Crackers 7oz", 4, 3.79)],
  [run("Choco Chip Cookies 13oz", 4, 4.19), run("Vanilla Creme Cookies 12oz", 4, 3.99)],
  [run("Trail Mix Nuts 6oz", 6, 4.99), run("Roasted Peanuts 6oz", 6, 3.49)],
];

export const PRESETS: Record<string, Preset> = {
  drinks: { header: "SOFT DRINKS", levels: DRINKS, neighbours: [JUICE, SNACKS] },
  snacks: { header: "SNACKS", levels: SNACKS, neighbours: [DRINKS, JUICE] },
};
