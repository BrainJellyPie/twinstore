import { expect, it } from "vitest";
import { classifyProduct } from "../productCatalog";

it.each([
  ["Thai Iced Tea", "teaCup"], ["Coconut Iced Coffee", "teaCup"],
  ["Turkish Coffee Cup", "cup"], ["Apple Tea Cup", "cup"], ["Ayran Yogurt Drink", "cup"],
])("renders prepared drink %s in its serving container", (name, kind) => {
  expect(classifyProduct(name)).toMatchObject({ kind, category: "drink", lieFlatInChest: false });
  expect(classifyProduct(`  ${name.toUpperCase()}  `)).toEqual(classifyProduct(name));
});

it.each(["Stainless Pet Bowl", "Collapsible Travel Pet Bowl", "Pet Feeding Bowl", "Camping Mug"])("keeps %s separate from prepared food", (name) => {
  expect(classifyProduct(name)).toMatchObject({ kind: "cup", category: "other", lieFlatInChest: false });
});

it.each([
  "Adjustable Dog Harness", "Retractable Dog Leash", "Reflective Pet Collar", "Cat Scratching Pad", "Foldable Pet Carrier",
  "Pet Grooming Brush", "Pet Nail Clippers", "Washable Pet Bed", "Pet Waste Bags 60pk", "Puzzle Treat Feeder",
  "Compact Camping Lantern", "Foldable Camp Chair", "Lightweight Daypack", "Trekking Pole Pair", "Insulated Picnic Bag",
  "Camping Cookware Set", "Dry Bag 10L", "Hiking Compass", "Emergency Rain Poncho", "Reflective Trail Vest", "Microfiber Travel Towel",
])("keeps non-food accessory %s out of edible categories", (name) => {
  const spec = classifyProduct(name);
  expect(spec.category).toBe("other");
  expect([spec.w, spec.h, spec.d].every((size) => Number.isFinite(size) && size > 0 && size < 0.5)).toBe(true);
});

it.each([
  ["Thai Milk Tea", "teaCup", "drink"], ["Thai Iced Tea 500ml", "bottle", "drink"],
  ["Bottled Coconut Coffee 250ml", "bottle", "drink"], ["Apple Juice 1L", "bottle", "drink"],
  ["Chocolate Milk", "bottle", "drink"], ["Chicken Pad Thai Bowl", "cup", "noodle"],
  ["Tom Yum Soup Cup", "cup", "pantry"], ["Bulgur Pilaf Bowl", "cup", "noodle"],
])("preserves existing food and retail beverage classification for %s", (name, kind, category) => {
  expect(classifyProduct(name)).toMatchObject({ kind, category });
});
