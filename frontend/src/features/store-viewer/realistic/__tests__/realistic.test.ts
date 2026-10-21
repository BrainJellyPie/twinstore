import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { createPackageGeometry } from "../productGeometries";
import type { CustomerResult, Rack, Slot, SlotItem } from "@/shared/types/domain";
import { classifyProduct, hashString, luminance, productPalette, splitLabel } from "../productCatalog";
import { atlasGrid, cellUv } from "../atlasLayout";
import { planFixture, faceTangent, FACE_NORMAL } from "../fixtureSpecs";
import { layoutProducts } from "../productLayout";
import { activeShoppers, angleDelta, facingForEvent, shopperPoseAt } from "../shopperPose";
import { createClock, stepClock } from "../playbackClock";

const item = (name: string, price = 249, promo = ""): SlotItem => ({ sku: name, name, price, promo });

function rack(partial: Partial<Rack> & Pick<Rack, "id" | "type" | "position">): Rack {
  return {
    shape: [[1]],
    rotation: 0,
    levels: 4,
    dwell_min: 5,
    dwell_max: 30,
    rack_name: partial.id,
    rack_desc: "",
    rack_decoration_desc: "",
    locked_faces: [],
    slots: [],
    ...partial,
  };
}

function slots(face: Slot["face"], names: string[][]): Slot[] {
  return names.map((row, i) => ({ block: 0, face, level: i + 1, items: row.map((n) => item(n)) }));
}

describe("productCatalog", () => {
  it.each([
    ["Aquafina Purified Water 20oz", "bottle"],
    ["Coca-Cola Classic 1 Liter", "bottle"],
    ["Monster Energy Green 16oz", "can"],
    ["Red Bull Energy Drink 8.4oz", "can"],
    ["Doritos Nacho Cheese 2.75oz", "bag"],
    ["Nissin Cup Noodles Chicken 2.25oz", "cup"],
    ["Maruchan Ramen Noodle Soup Beef 3oz", "bag"],
    ["Haagen-Dazs Vanilla 14oz", "pint"],
    ["Kellogg's Froot Loops Box 10.1oz", "box"],
    ["Pringles Original 5.2oz", "tube"],
    ["Nutella Hazelnut Spread 13oz", "jar"],
    ["DiGiorno Personal Pan Pepperoni Pizza", "box"],
    ["Bananas", "banana"],
    [" Organic Bananas 1kg ", "banana"],
    ["Banana Bunch", "banana"],
    ["Banana Bread", "bag"],
    ["Banana Chips", "bag"],
    ["Banana Milk", "bottle"],
    ["Banana Ice Cream", "pint"],
    ["Avocado", "avocado"],
    ["Fresh Avocados", "avocado"],
    ["Organic Hass Avocado Each", "avocado"],
    ["Ripe Avocados 1kg", "avocado"],
    ["Avocado Oil", "bottle"],
    ["Avocado Spread", "jar"],
    ["Avocado Chips", "bag"],
    ["Avocado Smoothie", "bottle"],
    ["Avocados 2pk", "box"],
    ["Avocado Halves", "box"],
    ["Green Avocado", "box"],
    ["Onion", "onion"],
    ["Yellow Onions", "onion"],
    ["Organic Brown Onions 500g", "onion"],
    ["Fresh Whole Onions Each", "onion"],
    ["Onions .25 lb", "onion"],
    [" ONIONS 0.5 kg ", "onion"],
    ["Brown Onion Loose", "onion"],
    ["Onions 1.5 lbs", "onion"],
    ["Lemon", "lemon"],
    ["Fresh Lemons", "lemon"],
    ["Organic Whole Lemon Each", "lemon"],
    ["Yellow Eureka Lemons 500g", "lemon"],
    [" Ripe Lemons 0.5 kg ", "lemon"],
    ["LEMONS .25 lb", "lemon"],
    ["Lemons 1.5 lbs", "lemon"],
    ["Lemon Juice", "bottle"],
    ["Lemonade", "bottle"],
    ["Lemon Iced Tea", "bottle"],
    ["Apples", "apple"],
    ["Organic Gala Apples 1kg", "apple"],
    ["Fuji Apple Each", "apple"],
    ["Apples 2pk", "applePair"],
    ["Red Apples 2-pack", "applePair"],
    ["Apples 4pk", "box"],
    ["Green Apples", "box"],
    ["Apple Juice", "bottle"],
    ["Apple Chips", "bag"],
    ["Apple Pie", "box"],
    ["Watering Can 5L", "wateringCan"],
    ["Metal Watering Can 5 L", "wateringCan"],
    ["Galvanized Watering Can", "wateringCan"],
    ["Watering Can 10L", "can"],
    ["Plastic Watering Can 5L", "can"],
    ["Watering Can 5L 2pk", "can"],
    ["Soda Can", "can"],
    ["Water Bottle", "bottle"],
    ["Croissant", "croissant"],
    ["Fresh Butter Croissant", "croissant"],
    ["Plain Croissant Each", "croissant"],
    ["French Croissants", "croissant"],
    ["Croissants 4pk", "box"],
    ["Chocolate Croissant", "box"],
    ["Ham Cheese Croissant", "box"],
    ["Croissant Sandwich", "box"],
    ["Terracotta Pot 20cm", "pot"],
    ["Clay Plant Pot 12.5 cm", "pot"],
    ["Terra Cotta Planter", "pot"],
    ["Terracotta Pot 4pk", "box"],
    ["Terracotta Pot 0cm", "box"],
    ["Terracotta Pot 100cm", "box"],
    ["Clay Mask", "box"],
    ["Cooking Pot", "box"],
    ["Potting Mix", "bag"],
  ])("classifies %s as %s", (name, kind) => {
    expect(classifyProduct(name).kind).toBe(kind);
  });

  it("sizes terracotta pots from the stated diameter while preserving the source shape", () => {
    expect(classifyProduct("Terracotta Pot 20cm").w).toBe(0.2);
    expect(classifyProduct("Clay Plant Pot 12.5 cm").w).toBe(0.125);
    expect(classifyProduct("Terracotta Planter").w).toBe(0.2);
  });

  it.each([
    "Lemons 2pk", "Lemons 2-pack", "Lemons 3 count", "Lemons 1kg 2pk",
    "Lemon Halves", "Lemon Slices", "Lemon Zest", "Lemon Curd", "Lemon Oil",
    "Preserved Lemons", "Dried Lemons", "Meyer Lemon", "Lemon Cookies",
    "Lemon Soap", "Lemon Scented Cleaner", "Lemongrass", "Lemonade Powder",
    "Lemons 0kg", "Lemons 0.00 g", "Lemons -1kg", "Lemons NaN kg", "Lemons Infinity kg", "Lemons 1e3g",
  ])("does not turn %s into an individual whole lemon", (name) => {
    expect(classifyProduct(name).kind).not.toBe("lemon");
  });

  it("does not mistake chocolate for cola or candy bars for milk", () => {
    expect(classifyProduct("Clif Bar Chocolate Chip 2.4oz").kind).not.toBe("bottle");
    expect(classifyProduct("Hershey's Milk Chocolate King Size 2.6oz").category).toBe("candy");
    expect(classifyProduct("Snickers Ice Cream Bar").category).toBe("icecream");
  });

  it("lays frozen trays and novelties flat in chest freezers", () => {
    expect(classifyProduct("Banquet Salisbury Steak Meal 11.8oz").lieFlatInChest).toBe(true);
    expect(classifyProduct("Haagen-Dazs Vanilla 14oz").lieFlatInChest).toBe(false);
  });

  it("hashes and colours deterministically with readable ink", () => {
    expect(hashString("Pepsi 20oz")).toBe(hashString("Pepsi 20oz"));
    expect(hashString("Pepsi 20oz")).not.toBe(hashString("Pepsi 1 Liter"));
    const a = productPalette("Lay's Classic 2.625oz");
    expect(productPalette("Lay's Classic 2.625oz")).toEqual(a);
    expect(a.base).toMatch(/^#[0-9a-f]{6}$/);
    for (const name of ["Smartwater 1L", "Takis Fuego 9.9oz", "Breyers Natural Vanilla 16oz"]) {
      const p = productPalette(name);
      const contrast = (Math.max(luminance(p.base), luminance(p.ink)) + 0.05) / (Math.min(luminance(p.base), luminance(p.ink)) + 0.05);
      expect(contrast).toBeGreaterThan(2.5);
    }
  });

  it("splits labels into brand, detail and size", () => {
    expect(splitLabel("Coca-Cola Classic 20oz")).toEqual({ brand: "Coca-Cola", detail: "Classic", size: "20oz" });
    expect(splitLabel("Ben & Jerry's Half Baked Pint").brand).toBe("Ben & Jerry's");
    expect(splitLabel("Red Bull Energy Drink 8.4oz")).toEqual({ brand: "Red Bull", detail: "Energy Drink", size: "8.4oz" });
    expect(splitLabel("Sprite 1 Liter").size).toBe("1 Liter");
  });
});

describe("atlasLayout", () => {
  it("fits cells in a power-of-two texture without overlap", () => {
    const g = atlasGrid(224, 128, 128);
    expect(g.cols * g.rows).toBeGreaterThanOrEqual(224);
    expect(Math.log2(g.width) % 1).toBe(0);
    expect(g.width).toBeLessThanOrEqual(4096);
    const a = cellUv(g, 0);
    const b = cellUv(g, 1);
    expect(b.offset[0] - a.offset[0]).toBeCloseTo(a.scale[0]);
    const last = cellUv(g, 223);
    expect(last.offset[1]).toBeGreaterThanOrEqual(0);
    expect(last.offset[0] + last.scale[0]).toBeLessThanOrEqual(1 + 1e-9);
  });

  it("shrinks cells to stay within the texture limit", () => {
    const g = atlasGrid(5000, 128, 128);
    expect(g.width).toBeLessThanOrEqual(4096);
    expect(g.height).toBeLessThanOrEqual(4096);
    expect(g.cols * g.rows).toBeGreaterThanOrEqual(5000);
  });
});

describe("fixture planning and product layout", () => {
  const gondola = rack({
    id: "g",
    type: "shelf",
    position: [3, 2],
    slots: [
      ...slots("N", [["Doritos Cool Ranch 2.75oz", "Lay's Classic 2.625oz"], ["Pringles Original 5.2oz"]]),
      ...slots("S", [["Snickers King Size 3.29oz"]]),
    ],
  });
  const wallFridge = rack({
    id: "f",
    type: "fridge",
    position: [2, 0],
    slots: slots("S", [["Pepsi 20oz", "Diet Coke 20oz"], ["Monster Energy Green 16oz"]]),
  });
  const chest = rack({ id: "c", type: "fridge", design_variant: "b", position: [2, 5], slots: slots("N", [["Haagen-Dazs Vanilla 14oz"]]) });

  it("tangent is the shopper's right hand", () => {
    // Facing a south face you look north (-Z); east (+X) is on your right.
    expect(faceTangent("S")).toEqual([1, 0]);
    expect(faceTangent("N")).toEqual([-1, 0]);
    const [nx, nz] = FACE_NORMAL.E;
    const [tx, tz] = faceTangent("E");
    expect(nx * tx + nz * tz).toBe(0);
  });

  it("plans double-sided gondolas, wall fridges and chests", () => {
    const g = planFixture(gondola, 8, 6);
    expect(g.kind).toBe("gondola");
    expect(g.layout).toBe("double");
    expect(g.banks.map((b) => b.face).sort()).toEqual(["N", "S"]);
    expect(g.banks[0]!.shelfYs).toHaveLength(4);
    const f = planFixture(wallFridge, 8, 6);
    expect(f.kind).toBe("reachIn");
    expect(f.layout).toBe("single");
    expect(planFixture(chest, 8, 6).kind).toBe("chest");
  });

  it("stocks every item inside its rack footprint with one price tag each", () => {
    const plans = [gondola, wallFridge, chest].map((r) => planFixture(r, 8, 6));
    const out = layoutProducts(plans, { maxRows: 3 });
    const items = [gondola, wallFridge, chest].flatMap((r) => r.slots.flatMap((s) => s.items));
    expect(out.tags).toHaveLength(items.length);
    expect(out.products.length).toBeGreaterThan(items.length);
    for (const it of items) expect(out.products.some((p) => p.name === it.name)).toBe(true);
    for (const p of out.products) {
      const r = [gondola, wallFridge, chest].find((x) => x.slots.some((s) => s.items.some((i) => i.name === p.name)))!;
      expect(p.x).toBeGreaterThanOrEqual(r.position[0] - 0.01);
      expect(p.x).toBeLessThanOrEqual(r.position[0] + 1.01);
      expect(p.z).toBeGreaterThanOrEqual(r.position[1] - 0.01);
      expect(p.z).toBeLessThanOrEqual(r.position[1] + 1.01);
      expect(p.sx).toBeGreaterThan(0);
    }
    // Chest stock lies inside the bin, below the lids.
    const pint = out.products.find((p) => p.name.startsWith("Haagen"))!;
    expect(pint.y).toBeGreaterThan(0.3);
    expect(pint.y + pint.sy).toBeLessThan(0.7);
  });

  it("emits a shelf talker for promo items", () => {
    const promo = rack({ id: "p", type: "shelf", position: [5, 3], slots: [{ block: 0, face: "S", level: 3, items: [item("Oreo King Size 4.1oz", 269, "2 for $5")] }] });
    const out = layoutProducts([planFixture(promo, 8, 6)], { maxRows: 2 });
    expect(out.talkers).toHaveLength(1);
    expect(out.talkers[0]!.promo).toBe("2 for $5");
  });

  it.each([
    ["Terracotta Pot 20cm", "pot", 0.2, 0.2 * (0.5314331 / 0.4662051), 0.2],
    ["Watering Can 5L", "wateringCan", 0.45233607, 0.19681853, 0.19101861],
    ["Avocado", "avocado", 0.09518591, 0.14323448, 0.09456679],
    ["Lemon", "lemon", 0.09536931, 0.06868193, 0.06826009],
    ["Yellow Onion", "onion", 0.07248241, 0.08637568, 0.06863658],
    ["Kiwi", "kiwi", 0.09006310, 0.06951961, 0.06862716],
    ["Ginger Root", "ginger", 0.20110649, 0.05158130, 0.08397771],
    ["Asian Pear", "asianPear", 0.04344488, 0.06696554, 0.04342672],
    ["Sweet Potato", "sweetPotato", 0.10046297, 0.05812428, 0.06098930],
    ["Croissant", "croissant", 0.2, 0.06199567, 0.07551152],
    ["Bananas", "banana", 0.134, 0.179, 0.223],
    ["Apples", "apple", 0.09756, 0.08539, 0.09590],
    ["Apples 2pk", "applePair", 0.20112, 0.08539, 0.09590],
  ] as const)("keeps %s proportional and in one layer on a shelf", (name, kind, width, height, depth) => {
    const produce = rack({ id: "produce", type: "shelf", position: [3, 3], slots: slots("S", [[name]]) });
    const out = layoutProducts([planFixture(produce, 8, 6)], { maxRows: 3 });
    expect(out.products.length).toBeGreaterThan(1);
    expect(new Set(out.products.map((p) => p.y)).size).toBe(1);
    expect(out.tags).toHaveLength(1);
    for (const p of out.products) {
      expect(p.kind).toBe(kind);
      expect(p.sx / p.sy).toBeCloseTo(width / height);
      expect(p.sz / p.sy).toBeCloseTo(depth / height);
    }
  });

  it.each(["Terracotta Pot 20cm", "Croissant", "Watering Can 5L", "Avocado", "Lemon", "Yellow Onion", "Kiwi", "Sweet Potato", "Asian Pear", "Ginger Root"])("keeps %s in a single layer on display tables", (name) => {
    const table = rack({ id: "pots", type: "table", position: [3, 3], slots: slots("S", [[name]]) });
    const out = layoutProducts([planFixture(table, 8, 6)], { maxRows: 3 });
    expect(out.products.length).toBeGreaterThan(0);
    expect(new Set(out.products.map((p) => p.y)).size).toBe(1);
  });

  it.each([0, 1] as const)("keeps the fallback pot open at detail %s", (detail) => {
    const geometry = createPackageGeometry("pot", detail);
    const material = new THREE.MeshBasicMaterial();
    const mesh = new THREE.Mesh(geometry, material);
    const ray = new THREE.Raycaster(new THREE.Vector3(0.01, 2, 0.01), new THREE.Vector3(0, -1, 0));
    const hits = ray.intersectObject(mesh);
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0]!.point.y).toBeCloseTo(0.12);
    geometry.dispose(); material.dispose();
  });

  it("carries SKU photos into every shelf facing and freezer stack", () => {
    const photographed = structuredClone([gondola, chest]);
    for (const fixture of photographed) {
      for (const slot of fixture.slots) {
        for (const product of slot.items) product.image_url = `/api/images/${encodeURIComponent(product.sku)}?v=photo`;
      }
    }
    const out = layoutProducts(photographed.map((fixture) => planFixture(fixture, 8, 6)), { maxRows: 3 });
    expect(out.products.length).toBeGreaterThan(2);
    for (const product of out.products) {
      expect(product.imageUrl).toBe(`/api/images/${encodeURIComponent(product.name)}?v=photo`);
    }
  });
});

describe("shopper pose and playback clock", () => {
  const ev = (elapsed_sec: number, x: number, y: number, action: string, face: CustomerResult["timeline"][number]["face"] = null) => ({
    elapsed_sec, x, y, action, duration: 0, target_rack: "", face, description: action, product_sku: "", product_name: "", price: 0,
  });
  const customer: CustomerResult = {
    persona_id: "p1",
    day: 1,
    arrival_time: "08:00:00",
    leave_time: "",
    total_spent: 0,
    timeline: [ev(0, 0, 3, "enter"), ev(10, 2, 3, "move"), ev(20, 2, 3, "browse", "S"), ev(40, 0, 3, "exit")],
  };
  const t0 = 8 * 3600;

  it("interpolates position and heading between events", () => {
    const pose = shopperPoseAt(customer, t0 + 5)!;
    expect(pose.x).toBeCloseTo(1.5);
    expect(pose.z).toBeCloseTo(3.5);
    expect(pose.moving).toBe(true);
    expect(pose.heading).toBeCloseTo(Math.PI / 2); // walking +X
  });

  it("looks at the shelf face while browsing and disappears after exit", () => {
    const pose = shopperPoseAt(customer, t0 + 25)!;
    expect(pose.moving).toBe(true); // heading back to the exit tile
    const still = shopperPoseAt({ ...customer, timeline: customer.timeline.slice(0, 3) }, t0 + 25)!;
    expect(still.moving).toBe(false);
    expect(Math.abs(angleDelta(still.lookYaw, Math.PI))).toBeLessThan(1e-9); // S face → look -Z
    expect(shopperPoseAt(customer, t0 - 1)).toBeNull();
    expect(shopperPoseAt(customer, t0 + 41)).toBeNull();
    expect(activeShoppers([customer], 1, t0 + 5)).toHaveLength(1);
    expect(activeShoppers([customer], 2, t0 + 5)).toHaveLength(0);
  });

  it("orients bodies toward shelves without requiring a speech description", () => {
    const event = { ...ev(20, 2, 3, "browse", "S"), description: "" };
    expect(facingForEvent(Math.PI / 2, false, event)).toBe(Math.PI);
    expect(facingForEvent(Math.PI / 2, true, event)).toBe(Math.PI / 2);
    expect(facingForEvent(Math.PI / 2, false, { ...event, face: null })).toBe(Math.PI / 2);
    expect(angleDelta(Math.PI - 0.01, -Math.PI + 0.01)).toBeCloseTo(0.02);
  });

  it("mirrors the playback clock from the published minute", () => {
    const c = createClock();
    const base = { playing: true, speed: 60, day: 1, finished: false, minTime: t0, maxTime: t0 + 3600 };
    expect(stepClock(c, 0.016, { ...base, currentMinute: t0 })).toBe(t0);
    let t = 0;
    for (let i = 0; i < 30; i++) t = stepClock(c, 0.1, { ...base, currentMinute: t0 });
    // 30 × 0.1 s × 60 = 180 s, but the loop's time stays within the published
    // minute (+ one frame of slack) until the next minute is published.
    expect(t).toBe(t0 + 66);
    t = stepClock(c, 0.1, { ...base, currentMinute: t0 + 60 });
    expect(t).toBe(t0 + 72);
    // A seek publishes a far-away minute: the clock jumps into that minute.
    t = stepClock(c, 0.1, { ...base, playing: false, currentMinute: t0 + 1800 });
    expect(t).toBe(t0 + 1800);
  });
});
