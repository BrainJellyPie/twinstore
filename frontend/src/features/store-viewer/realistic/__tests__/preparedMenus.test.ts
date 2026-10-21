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

it.each(["Mango Lassi", "Vietnamese Iced Coffee", "Lemongrass Iced Tea", "Iced Mocha"])("shows the prepared drink %s in a takeaway cup", (name) => {
  expect(classifyProduct(name)).toMatchObject({ kind: "teaCup", category: "drink", lieFlatInChest: false });
});
it("keeps hot masala chai a drink in a small cup", () => {
  expect(classifyProduct("Masala Chai Cup")).toMatchObject({ kind: "cup", category: "drink", lieFlatInChest: false });
});
it.each(["Butter Chicken Curry Bowl", "Chickpea Chana Masala Bowl", "Palak Paneer Bowl", "Lentil Dal Bowl",
  "Vegetable Biryani Bowl", "Chicken Biryani Bowl", "Beef Pho Noodle Bowl", "Chicken Pho Noodle Bowl",
  "Vegetable Pho Noodle Bowl", "Lemongrass Chicken Rice Bowl", "Tofu Vermicelli Bowl"])("keeps %s in an upright shallow bowl", (name) => {
  const product = classifyProduct(name);
  expect(product.kind).toBe("cup"); expect(product.h).toBeLessThan(product.w); expect(product.lieFlatInChest).toBe(false);
});
it.each(["Garlic Naan 2pc", "Vegetable Samosa 2pc", "Cucumber Raita Cup", "Gulab Jamun 2pc", "Grilled Pork Banh Mi",
  "Tofu Banh Mi", "Fresh Summer Rolls 2pc", "Crispy Spring Rolls 3pc", "Coconut Rice Pudding Cup"])("keeps dish %s out of drink and whole-produce categories", (name) => {
  expect(["drink", "produce"]).not.toContain(classifyProduct(name).category);
});
it.each(["Mango Juice 350ml", "Iced Coffee 250ml", "Milk 1L"])("preserves bottled retail drinks: %s", (name) => {
  expect(classifyProduct(name)).toMatchObject({ kind: "bottle", category: "drink" });
});

it("does not turn mocha chocolate into a coffee drink", () => {
  expect(classifyProduct("Mocha Chocolate Bar")).toMatchObject({ kind: "bag", category: "candy" });
});
