import { expect, it } from "vitest";
import { classifyProduct } from "../productCatalog";

it.each(["Beef Burrito Bowl", "Greek Salad Bowl", "Tabbouleh Salad Bowl", "Lentil & Herb Bowl", "Grilled Vegetable Bowl"])("shows prepared menu %s in a bowl", (name) => {
  const product = classifyProduct(name);
  expect(product.kind).toBe("cup");
  expect(product.h).toBeLessThan(product.w);
  expect(product.lieFlatInChest).toBe(false);
});
it.each(["Frozen Beef Burrito", "Bean Burrito 6pk", "Corn Dog 4pk"])("preserves the frozen package for %s", (name) => {
  expect(classifyProduct(name)).toMatchObject({ kind: "bag", category: "frozen", lieFlatInChest: true });
});
it.each(["Falafel Pita Wrap", "Grilled Chicken Pita", "Roasted Vegetable Pita", "Hummus & Pita Plate", "Baba Ganoush & Pita Plate",
  "Chicken Rice Plate", "Stuffed Vine Leaves 6pc", "Olive & Feta Side", "Baklava 2pc", "Chicken Burrito", "Bean & Rice Burrito",
  "Chicken Tacos 3pc", "Mushroom Tacos 3pc", "Cheese Quesadilla", "Chicken Quesadilla", "Loaded Nachos", "Guacamole & Tortilla Chips",
  "Corn & Lime Side", "Cinnamon Churros 3pc"])("keeps prepared dish %s out of drink and whole-produce categories", (name) => {
  const product = classifyProduct(name);
  expect(["drink", "produce"]).not.toContain(product.category);
  expect([product.w, product.h, product.d].every((size) => Number.isFinite(size) && size > 0 && size < 0.4)).toBe(true);
});
