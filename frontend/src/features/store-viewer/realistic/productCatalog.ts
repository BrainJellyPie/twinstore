// Pure helpers that turn a product name into a package: geometry kind, real-world
// size, colours and label text. No three.js / DOM dependencies so they can be
// unit-tested and reused by an offline renderer.

export type PackageKind = "bottle" | "perfumeBottle" | "teaCup" | "can" | "cup" | "pint" | "jar" | "tube" | "box" | "bag" | "banana" | "apple" | "applePair" | "avocado" | "lemon" | "onion" | "kiwi" | "sweetPotato" | "asianPear" | "ginger" | "pot" | "croissant" | "burgerBun" | "wateringCan";

export type ProductCategory =
  | "drink"
  | "icecream"
  | "frozen"
  | "snack"
  | "candy"
  | "noodle"
  | "pantry"
  | "bakery"
  | "produce"
  | "other";

export interface PackageSpec {
  kind: PackageKind;
  // Real-world size in metres: width (facing), height, depth.
  w: number;
  h: number;
  d: number;
  category: ProductCategory;
  // Flat packs (frozen trays, novelty bars) lie face-up in chest freezers.
  lieFlatInChest: boolean;
}

// FNV-1a 32-bit — stable across sessions and platforms.
export function hashString(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

// Deterministic pseudo-random in [0, 1) from a string key and a salt.
export function hash01(key: string, salt = 0): number {
  let h = hashString(key) ^ Math.imul(salt + 1, 0x9e3779b1);
  h = Math.imul(h ^ (h >>> 16), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

function spec(
  kind: PackageKind,
  w: number,
  h: number,
  d: number,
  category: ProductCategory,
  lieFlatInChest = false,
): PackageSpec {
  return { kind, w, h, d, category, lieFlatInChest };
}

function has(n: string, re: RegExp): boolean {
  return re.test(n);
}

function bottleSize(n: string): [number, number] {
  if (has(n, /\b2\s?(l|liter|litre)\b/)) return [0.11, 0.33];
  if (has(n, /\b1(\.0)?\s?(l|liter|litre)\b|33\.8\s?oz|1l\b/)) return [0.085, 0.29];
  if (has(n, /\b(28|32)\s?oz/)) return [0.08, 0.26];
  if (has(n, /\b(20|23|24|23\.9)\s?oz/)) return [0.068, 0.23];
  if (has(n, /\b(16\.9|16|18\.5|15\.2|14|13\.7|15\.9)\s?oz/)) return [0.066, 0.2];
  if (has(n, /\b(12|11\.5|10|8|7|6\.75)\s?oz/)) return [0.06, 0.165];
  return [0.068, 0.23];
}

function canSize(n: string): [number, number] {
  if (has(n, /8\.4\s?oz/)) return [0.053, 0.135];
  if (has(n, /\b(23|24|22|25)\s?oz/)) return [0.073, 0.2];
  if (has(n, /\b(16|15\.5|16\.9|19\.2)\s?oz/)) return [0.066, 0.157];
  return [0.066, 0.122];
}

type Rule = [RegExp, (n: string) => PackageSpec];

// Ordered: first match wins. Ice-cream novelties precede candy ("Snickers Ice
// Cream Bar"), candy precedes drinks ("Milk Chocolate"), cups precede noodles.
const RULES: Rule[] = [
  // Specialty packaging precedes food words such as tea, milk, jelly and oil.
  [/\b(?:fragrance|perfume)\b.*\bset\b/, () => spec("box", 0.16, 0.12, 0.045, "other")],
  [/\b(?:fragrance|perfume)\b.*\bpouch\b/, () => spec("bag", 0.11, 0.14, 0.025, "other")],
  [/\beau de (?:toilette|parfum)\b|\bperfume oil\b/, (n) =>
    has(n, /\b(?:5|10|15)\s*ml\b/)
      ? spec("perfumeBottle", 0.032, 0.08, 0.024, "other")
      : spec("perfumeBottle", 0.055, 0.12, 0.035, "other")],
  [/\bperfume atomizer\b|\bamber travel spray\b/, () => spec("bottle", 0.022, 0.095, 0.022, "other")],
  [/\bbody mist\b|\broom spray\b|\breed diffuser\b/, () => spec("bottle", 0.055, 0.18, 0.055, "other")],
  [/\bcandle(?:\s+\d+(?:\.\d+)?\s*g)?$/, () => spec("jar", 0.075, 0.09, 0.075, "other")],
  [/\b(?:dish soap|laundry liquid)\s+refill\b/, () => spec("bag", 0.12, 0.2, 0.05, "other")],
  [/\b(?:oats|rice|lentils|chickpeas|pasta|nuts|seeds|coffee|tea)\b.*\brefill\s+\d+(?:\.\d+)?\s*(?:kg|g)\b/,
    () => spec("bag", 0.13, 0.2, 0.06, "pantry")],
  [/^mini milk tea tasting set$/, () => spec("box", 0.18, 0.12, 0.1, "drink")],
  [/^(?:classic pearl milk tea|brown sugar pearl milk|taro milk tea|matcha pearl latte|thai milk tea|jasmine milk tea|mango fruit tea|passion fruit green tea|peach oolong tea|lychee coconut jelly tea|oat milk pearl tea)(?:\s+\d+(?:\.\d+)?\s*(?:ml|oz))?$/,
    () => spec("teaCup", 0.095, 0.23, 0.095, "drink")],
  [/^(?:mango lassi|vietnamese iced coffee|lemongrass iced tea|iced mocha|thai iced tea|coconut iced coffee)$/,
    () => spec("teaCup", 0.095, 0.23, 0.095, "drink")],
  [/^(?:masala chai cup|apple tea cup)$/, () => spec("cup", 0.085, 0.11, 0.085, "drink")],
  [/^turkish coffee cup$/, () => spec("cup", 0.065, 0.075, 0.065, "drink")],
  [/^ayran yogurt drink$/, () => spec("cup", 0.09, 0.13, 0.09, "drink")],
  // Empty pet bowls and camping drinkware are merchandise, not prepared meals.
  [/^(?:stainless pet bowl|collapsible travel pet bowl|pet feeding bowl)$/, () => spec("cup", 0.12, 0.055, 0.12, "other")],
  [/^camping mug$/, () => spec("cup", 0.085, 0.1, 0.085, "other")],
  // Garden tools must precede beverage-can and water-bottle rules.
  [/^(?:(?:metal|galvanized)\s+)?watering can(?:\s+5\s*l)?$/,
    () => spec("wateringCan", 0.45233607, 0.19681853, 0.19101861, "other")],
  [
    /ice cream bar|ice cream sandwich|popsicle|bomb pop|drumstick|klondike|mochi|good humor|fatboy|outshine|fruit bar|\bcone\b|cookie sandwich|dessert sandwich|ice cream cone|haagen-dazs.*\bbar\b|almond bar/,
    () => spec("bag", 0.075, 0.2, 0.035, "icecream", true),
  ],
  [
    /\bpint\b|haagen|ben & jerry|breyers|halo top|talenti|ice cream|gelato/,
    () => spec("pint", 0.09, 0.105, 0.09, "icecream"),
  ],
  [/pizza\b|deep dish/, () => spec("box", 0.22, 0.22, 0.05, "frozen", true)],
  // The prepared cantina bowl is served in a container, unlike frozen wraps.
  [/^beef burrito bowl$/, () => spec("cup", 0.12, 0.075, 0.12, "pantry")],
  [/burrito|corn dog/, () => spec("bag", 0.085, 0.17, 0.045, "frozen", true)],
  [/fries|crinkles|tots\b|vegetables|any'tizers|popcorn chicken|nuggets/, () => spec("bag", 0.2, 0.28, 0.05, "frozen", true)],
  [
    /\bmeal\b|salisbury|fettuccine|hungry-man|hot pockets|waffles|eggo|frozen|sausage egg|biscuit\b|banquet|michelina|stouffer|lean cuisine|lasagna|mozzarella sticks|cheeseburgers|white castle/,
    () => spec("box", 0.19, 0.14, 0.045, "frozen", true),
  ],
  [/\bbowl\b/, () => spec("cup", 0.12, 0.075, 0.12, "noodle")],
  [/micro cup/, () => spec("cup", 0.09, 0.08, 0.09, "pantry")],
  [/cereal cup|crunch cup|cheerios cup|flakes cup|oatmeal.*cup|\bcup\b|instant lunch/, (n) =>
    has(n, /noodle|ramen|ramyun|nissin|instant lunch/)
      ? spec("cup", 0.095, 0.11, 0.095, "noodle")
      : spec("cup", 0.085, 0.1, 0.085, "pantry")],
  [/pouch/, () => spec("bag", 0.11, 0.14, 0.02, "pantry")],
  [/tuna/, () => spec("can", 0.085, 0.045, 0.085, "pantry")],
  [/spam\b/, () => spec("box", 0.1, 0.085, 0.06, "pantry")],
  [/6-pack|6 pack|multipack/, () => spec("box", 0.2, 0.13, 0.11, "noodle")],
  [/ramen|ramyun|mi goreng|ichiban|tom yum|yakisoba|udon/, () => spec("bag", 0.13, 0.17, 0.035, "noodle")],
  [
    /soup|campbell's chunky|chili with|chili con|hormel chili|stew|progresso|ravioli|meatballs|beans\b/,
    () => spec("can", 0.075, 0.11, 0.075, "pantry"),
  ],
  [
    /energy|red bull|monster|celsius|\bcans?\b|beer|seltzer|arizona/,
    (n) => {
      const [dia, h] = canSize(n);
      return spec("can", dia, h, dia, "drink");
    },
  ],

  [/pringles|stax/, () => spec("tube", 0.075, 0.23, 0.075, "snack")],
  [/1-minute oats|quick oats|old fashioned oats/, () => spec("tube", 0.13, 0.18, 0.13, "pantry")],
  [/iodized salt|table salt/, () => spec("tube", 0.085, 0.14, 0.085, "pantry")],
  [/\boil\b/, () => spec("bottle", 0.1, 0.3, 0.1, "pantry")],
  [/cooking spray|\bpam\b/, () => spec("tube", 0.055, 0.19, 0.055, "pantry")],
  [/\bchocolate\s+(?:bar|block)\b/, () => spec("bag", 0.075, 0.19, 0.022, "candy")],
  [
    /king size|candy|skittles|sour patch|gummies|gummy|goldbears|haribo|airheads|life savers|reese|snickers|kit kat|butterfinger|hershey|twix|m&m|starburst|swedish fish|trolli|crawlers|share size/,
    (n) =>
      has(n, /share size|gummies|gummy|goldbears|haribo|bag|swedish fish|trolli|crawlers/)
        ? spec("bag", 0.13, 0.18, 0.035, "candy")
        : spec("bag", 0.075, 0.19, 0.022, "candy"),
  ],
  [
    /peanut butter|jelly|\bjam\b|nutella|spread|mayonnaise|pasta sauce|salsa|prego|ragu/,
    () => spec("jar", 0.085, 0.13, 0.085, "pantry"),
  ],
  [/ketchup|mustard|redhot|hot sauce|sriracha|syrup|bbq sauce|\bsauce\b/, () => spec("bottle", 0.07, 0.19, 0.07, "pantry")],
  [
    /water|soda|\bcola\b|coca-cola|\bcoke\b|pepsi|sprite|dr pepper|mountain dew|fanta|7up|juice|lemonade|\btea\b|gatorade|powerade|bodyarmor|naked|frappuccino|pink drink|drink|\bmilk\b|core power|smoothie|kombucha|coffee|latte|vitaminwater|snapple|perrier|evian|fiji|essentia|dasani|aquafina|pure life|\bshake\b/,
    (n) => {
      const [dia, h] = bottleSize(n);
      return spec("bottle", dia, h, dia, "drink");
    },
  ],
  [/jerky/, () => spec("bag", 0.15, 0.22, 0.035, "snack")],
  [/meat stick|slim jim/, () => spec("bag", 0.045, 0.2, 0.02, "snack")],
  [/peanuts|seeds|corn nuts|\bnuts\b|trail mix|\bmix\b|pistachios|almonds|cashews/, () => spec("bag", 0.11, 0.16, 0.035, "snack")],
  [
    /chips|lay'?s|doritos|cheetos|fritos|ruffles|funyuns|takis|popcorn|smartfood|pretzel|pork rinds|baken-ets|bugles|munchies|combos|goldfish|cheez-it|crackers/,
    (n) =>
      has(n, /\b(1|2|2\.125|2\.25|2\.4|1\.5)\s?oz/)
        ? spec("bag", 0.14, 0.2, 0.05, "snack")
        : spec("bag", 0.165, 0.24, 0.06, "snack"),
  ],
  [
    /\bbars?\b|clif|\bkind\b|rxbar|belvita|nature valley|nutri-grain|fiber one|granola/,
    () => spec("bag", 0.065, 0.16, 0.02, "snack"),
  ],
  [/pop-tarts.*\b(8|12)ct|donettes|\bbox\b/, () => spec("box", 0.15, 0.21, 0.07, "bakery")],
  [
    /cookies?|oreo|chips ahoy|nutter butter|fig newtons|famous amos|brownie|cupcakes|twinkies|honey bun|muffin|creme pies|rice krispies|pop-tarts/,
    () => spec("bag", 0.12, 0.16, 0.035, "bakery"),
  ],
  [/cereal|cheerios|froot loops|frosted flakes|granola box/, () => spec("box", 0.19, 0.27, 0.065, "pantry")],
  // Singular rolls and explicit individual sales; unqualified plural buns stay packaged.
  [/^(?:(?:fresh|plain|unseeded)\s+)*(?:hamburger|burger)\s+(?:bun(?:\s+(?:each|loose|single))?|buns\s+(?:each|loose|single))$/,
    () => spec("burgerBun", 0.11082269, 0.05778436, 0.10592587, "bakery")],
  [/bread|\bbuns?\b|loaf|bagels/, () => spec("bag", 0.26, 0.13, 0.13, "bakery")],
  [/tortillas/, () => spec("bag", 0.22, 0.24, 0.03, "bakery")],
  [/pasta sides|knorr|rice-a-roni/, () => spec("bag", 0.13, 0.18, 0.04, "pantry")],
  [/sugar|flour/, () => spec("bag", 0.12, 0.18, 0.06, "pantry")],
  [/pasta\b|penne|spaghetti|macaroni|mac & cheese|\brice\b/, () => spec("box", 0.14, 0.23, 0.05, "pantry")],
  // Whole fresh produce only: flavored foods and packaged formats keep their rules.
  [/^(?:(?:fresh|organic|whole|raw)\s+)*ginger(?:\s+roots?)?(?:\s+(?:loose|each|(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("ginger", 0.20110649, 0.05158130, 0.08397771, "produce")],
  [/^(?:(?:fresh|organic|ripe|whole|raw)\s+)*(?:asian|nashi)(?:\s+|-)pears?(?:\s+(?:loose|each|(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("asianPear", 0.04344488, 0.06696554, 0.04342672, "produce")],
  [/^(?:(?:fresh|organic|raw|whole)\s+)*sweet(?:\s+|-)potato(?:es)?(?:\s+(?:loose|each|(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("sweetPotato", 0.10046297, 0.05812428, 0.06098930, "produce")],
  [/^(?:(?:fresh|organic|ripe|whole|green|hayward)\s+)*(?:kiwis?|kiwifruits?|kiwi\s+fruits?)(?:\s+(?:loose|each|(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("kiwi", 0.09006310, 0.06951961, 0.06862716, "produce")],
  [/^(?:(?:fresh|organic|whole|yellow|brown)\s+)*onions?(?:\s+(?:loose|each|(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("onion", 0.07248241, 0.08637568, 0.06863658, "produce")],
  [/^(?:(?:fresh|organic|ripe|whole|yellow|eureka)\s+)*lemons?(?:\s+(?:loose|each|(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("lemon", 0.09536931, 0.06868193, 0.06826009, "produce")],
  [/^(?:(?:fresh|organic|ripe|hass)\s+)*avocados?(?:\s+(?:loose|each|\d+(?:\.\d+)?\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("avocado", 0.09518591, 0.14323448, 0.09456679, "produce")],
  [/^(?:(?:fresh|organic|ripe|yellow|cavendish)\s+)*bananas?(?:\s+(?:bunch|loose|each|\d+(?:\.\d+)?\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("banana", 0.134, 0.179, 0.223, "produce")],
  [/^(?:(?:fresh|organic|red|gala|fuji|braeburn|pink lady|red delicious)\s+)*apples?\s+(?:2\s?(?:pk|pack)|2-pack)$/,
    () => spec("applePair", 0.20112, 0.08539, 0.09590, "produce")],
  [/^(?:(?:fresh|organic|red|gala|fuji|braeburn|pink lady|red delicious)\s+)*apples?(?:\s+(?:loose|each|\d+(?:\.\d+)?\s*(?:kg|g|lb|lbs)))?$/,
    () => spec("apple", 0.09756, 0.08539, 0.09590, "produce")],
  [/^(?:terracotta|terra cotta|clay) (?:plant )?(?:pot|planter)(?:\s+[1-9]\d?(?:\.\d+)?\s*cm)?$/,
    (n) => {
      const diameter = Number(n.match(/([1-9]\d?(?:\.\d+)?)\s*cm$/)?.[1] ?? 20) / 100;
      return spec("pot", diameter, diameter * (0.5314331 / 0.4662051), diameter, "other");
    }],
  [/^(?:(?:fresh|butter|plain|french)\s+)*croissants?(?:\s+(?:each|loose|single))?$/,
    () => spec("croissant", 0.2, 0.06199567, 0.07551152, "bakery")],
];

const DEFAULT_SPEC: PackageSpec = spec("box", 0.12, 0.18, 0.05, "other");

// Bundled image identities remain stable when products use localized or edited names.
const STARTER_PACKAGES: Record<string, PackageSpec[]> = { "starter-01": [
  spec("box", 0.075, 0.23, 0.075, "drink"), spec("jar", 0.085, 0.12, 0.085, "pantry"),
  spec("bag", 0.11, 0.16, 0.03, "pantry"), spec("bag", 0.13, 0.21, 0.055, "pantry"),
  spec("bottle", 0.075, 0.19, 0.075, "other"), spec("box", 0.09, 0.12, 0.03, "other"),
  spec("bottle", 0.065, 0.12, 0.065, "other"), spec("box", 0.065, 0.18, 0.025, "other"),
  DEFAULT_SPEC, DEFAULT_SPEC, DEFAULT_SPEC, spec("cup", 0.085, 0.1, 0.085, "other"),
  spec("bag", 0.17, 0.2, 0.09, "bakery"), spec("bottle", 0.068, 0.23, 0.068, "drink"),
  spec("bag", 0.165, 0.24, 0.06, "snack"), spec("jar", 0.075, 0.1, 0.075, "pantry"),
], "starter-02": [
  spec("bottle", 0.068, 0.23, 0.068, "drink"), spec("box", 0.075, 0.23, 0.075, "drink"),
  spec("bag", 0.165, 0.24, 0.06, "snack"), spec("cup", 0.095, 0.11, 0.095, "noodle"),
  spec("croissant", 0.2, 0.06199567, 0.07551152, "bakery"), spec("cup", 0.085, 0.1, 0.085, "pantry"),
  spec("bag", 0.12, 0.16, 0.035, "bakery"), spec("can", 0.085, 0.045, 0.085, "pantry"),
  spec("banana", 0.134, 0.179, 0.223, "produce"), spec("applePair", 0.20112, 0.08539, 0.09590, "produce"),
  spec("box", 0.12, 0.04, 0.09, "pantry"), spec("box", 0.25, 0.07, 0.11, "pantry"),
  spec("bottle", 0.075, 0.23, 0.075, "other"), spec("box", 0.2, 0.09, 0.11, "other"),
  spec("tube", 0.055, 0.16, 0.035, "other"), spec("tube", 0.11, 0.23, 0.11, "other"),
], "starter-03": [
  spec("box", 0.2, 0.16, 0.04, "other"), spec("box", 0.2, 0.2, 0.055, "other"),
  spec("box", 0.17, 0.12, 0.16, "other"), spec("bag", 0.2, 0.24, 0.035, "other"),
  spec("box", 0.13, 0.2, 0.025, "other"), spec("box", 0.15, 0.21, 0.03, "other"),
  spec("box", 0.07, 0.06, 0.035, "other"), spec("box", 0.075, 0.14, 0.02, "other"),
  spec("jar", 0.1, 0.19, 0.1, "other"), spec("jar", 0.075, 0.09, 0.075, "other"),
  spec("bag", 0.17, 0.24, 0.07, "other"), spec("bag", 0.11, 0.16, 0.035, "other"),
  spec("tube", 0.12, 0.3, 0.12, "other"), spec("tube", 0.075, 0.23, 0.075, "other"),
  spec("box", 0.16, 0.13, 0.025, "other"), spec("box", 0.14, 0.22, 0.1, "other"),
], "starter-04": [
  spec("bag", 0.13, 0.23, 0.07, "pantry"), spec("jar", 0.075, 0.12, 0.075, "pantry"),
  spec("box", 0.12, 0.13, 0.04, "produce"), spec("box", 0.19, 0.14, 0.045, "frozen", true),
  spec("cup", 0.12, 0.09, 0.12, "pantry"), spec("box", 0.16, 0.12, 0.05, "bakery"),
  spec("box", 0.15, 0.18, 0.02, "other"), spec("box", 0.04, 0.2, 0.025, "other"),
  spec("box", 0.05, 0.18, 0.012, "other"), spec("bag", 0.22, 0.2, 0.1, "other"),
  spec("box", 0.17, 0.17, 0.03, "other"), spec("box", 0.16, 0.13, 0.025, "other"),
  spec("box", 0.1, 0.08, 0.04, "other"), spec("box", 0.15, 0.08, 0.1, "other"),
  spec("box", 0.15, 0.15, 0.04, "other"), spec("bottle", 0.08, 0.23, 0.08, "other"),
], "starter-05": [
  spec("cup", 0.14, 0.08, 0.14, "pantry"), spec("box", 0.22, 0.04, 0.22, "bakery"),
  spec("box", 0.11, 0.1, 0.11, "bakery"), spec("cup", 0.14, 0.08, 0.14, "pantry"),
  spec("box", 0.14, 0.045, 0.09, "pantry"), spec("cup", 0.14, 0.08, 0.14, "pantry"),
  spec("bag", 0.1, 0.16, 0.07, "pantry"), spec("cup", 0.14, 0.08, 0.14, "noodle"),
  spec("cup", 0.14, 0.09, 0.14, "noodle"), spec("bag", 0.1, 0.16, 0.07, "pantry"),
  spec("teaCup", 0.095, 0.23, 0.095, "drink"), spec("bottle", 0.065, 0.18, 0.065, "drink"),
  spec("cup", 0.14, 0.08, 0.14, "produce"), spec("pot", 0.15, 0.13, 0.11, "drink"),
  spec("box", 0.08, 0.045, 0.08, "bakery"), spec("cup", 0.085, 0.07, 0.085, "drink"),
], "starter-06": [
  spec("box", 0.09, 0.12, 0.03, "other"), spec("box", 0.16, 0.04, 0.04, "other"),
  spec("box", 0.14, 0.05, 0.055, "other"), spec("bag", 0.18, 0.25, 0.12, "other"),
  spec("box", 0.04, 0.05, 0.04, "other"), spec("box", 0.12, 0.12, 0.01, "other"),
  spec("box", 0.1, 0.25, 0.03, "other"), spec("bottle", 0.13, 0.25, 0.1, "other"),
  spec("bag", 0.09, 0.13, 0.01, "other"), spec("tube", 0.1, 0.18, 0.1, "other"),
  spec("perfumeBottle", 0.055, 0.12, 0.035, "other"), spec("box", 0.2, 0.11, 0.2, "other"),
  spec("box", 0.15, 0.1, 0.01, "other"), spec("box", 0.148, 0.21, 0.015, "other"),
  spec("bag", 0.13, 0.2, 0.06, "pantry"), spec("bottle", 0.045, 0.12, 0.045, "other"),
], "starter-07": [
  spec("cup", 0.065, 0.065, 0.065, "drink"), spec("cup", 0.085, 0.12, 0.085, "drink"),
  spec("cup", 0.085, 0.1, 0.085, "drink"), spec("cup", 0.095, 0.075, 0.095, "drink"),
  spec("cup", 0.095, 0.075, 0.095, "drink"), spec("cup", 0.095, 0.075, 0.095, "drink"),
  spec("teaCup", 0.095, 0.18, 0.095, "drink"), spec("cup", 0.085, 0.13, 0.085, "drink"),
  spec("cup", 0.085, 0.13, 0.085, "drink"), spec("teaCup", 0.095, 0.16, 0.095, "drink"),
  spec("teaCup", 0.095, 0.16, 0.095, "drink"), spec("cup", 0.095, 0.09, 0.095, "drink"),
  spec("box", 0.09, 0.07, 0.09, "bakery"), spec("box", 0.1, 0.045, 0.1, "bakery"),
  spec("box", 0.07, 0.08, 0.07, "bakery"), spec("box", 0.09, 0.035, 0.09, "bakery"),
], "starter-08": [
  spec("bag", 0.12, 0.19, 0.05, "pantry"), spec("jar", 0.075, 0.13, 0.075, "pantry"),
  spec("bag", 0.15, 0.21, 0.04, "pantry"), spec("bag", 0.12, 0.18, 0.025, "pantry"),
  spec("bag", 0.07, 0.25, 0.04, "noodle"), spec("box", 0.16, 0.1, 0.025, "pantry"),
  spec("can", 0.07, 0.06, 0.07, "pantry"), spec("jar", 0.05, 0.1, 0.05, "pantry"),
  spec("box", 0.11, 0.06, 0.08, "pantry"), spec("box", 0.1, 0.04, 0.1, "pantry"),
  spec("box", 0.13, 0.035, 0.19, "pantry", true), spec("box", 0.13, 0.035, 0.19, "pantry", true),
  spec("cup", 0.08, 0.1, 0.08, "other"), spec("tube", 0.058, 0.09, 0.058, "other"),
  spec("cup", 0.08, 0.16, 0.08, "other"), spec("bag", 0.15, 0.15, 0.025, "other"),
], "starter-09": [
  spec("box", 0.13, 0.07, 0.1, "produce"), spec("bag", 0.06, 0.23, 0.05, "produce"),
  spec("bag", 0.14, 0.16, 0.12, "produce"), spec("bag", 0.07, 0.28, 0.04, "produce"),
  spec("bag", 0.18, 0.28, 0.07, "pantry"), spec("bag", 0.12, 0.2, 0.055, "pantry"),
  spec("jar", 0.08, 0.14, 0.08, "pantry"), spec("bag", 0.1, 0.1, 0.035, "pantry"),
  spec("box", 0.18, 0.05, 0.09, "pantry"), spec("box", 0.12, 0.12, 0.06, "pantry"),
  spec("bag", 0.075, 0.16, 0.015, "candy"), spec("bag", 0.1, 0.14, 0.025, "candy"),
  spec("bag", 0.07, 0.17, 0.07, "icecream", true), spec("box", 0.09, 0.055, 0.09, "bakery"),
  spec("box", 0.13, 0.065, 0.07, "bakery"), spec("bag", 0.13, 0.2, 0.14, "bakery"),
], "starter-10": [
  spec("box", 0.13, 0.3, 0.045, "other"), spec("box", 0.1, 0.25, 0.04, "other"),
  spec("box", 0.16, 0.14, 0.09, "other"), spec("box", 0.2, 0.15, 0.04, "other"),
  spec("box", 0.15, 0.05, 0.045, "other"), spec("box", 0.045, 0.04, 0.025, "other"),
  spec("box", 0.08, 0.08, 0.025, "other"), spec("box", 0.09, 0.14, 0.025, "other"),
  spec("bag", 0.18, 0.28, 0.11, "other"), spec("box", 0.18, 0.28, 0.08, "other"),
  spec("box", 0.06, 0.3, 0.035, "other"), spec("box", 0.08, 0.3, 0.025, "other"),
  spec("box", 0.2, 0.2, 0.15, "other"), spec("bag", 0.23, 0.23, 0.12, "other"),
  spec("box", 0.18, 0.2, 0.055, "other"), spec("box", 0.06, 0.22, 0.02, "other"),
], "starter-11": [
  spec("box", 0.06, 0.28, 0.02, "other"), spec("box", 0.07, 0.25, 0.035, "other"),
  spec("box", 0.2, 0.27, 0.035, "other"), spec("box", 0.2, 0.06, 0.2, "other"),
  spec("bottle", 0.13, 0.25, 0.08, "other"), spec("jar", 0.1, 0.15, 0.1, "other"),
  spec("jar", 0.06, 0.095, 0.06, "other"), spec("box", 0.09, 0.12, 0.025, "other"),
  spec("bag", 0.17, 0.26, 0.08, "other"), spec("bag", 0.17, 0.25, 0.07, "other"),
  spec("box", 0.28, 0.11, 0.025, "other"), spec("box", 0.065, 0.11, 0.035, "other"),
  spec("box", 0.13, 0.2, 0.08, "other"), spec("bag", 0.13, 0.15, 0.035, "other"),
  spec("cup", 0.13, 0.11, 0.13, "other"), spec("cup", 0.18, 0.05, 0.18, "other"),
], "starter-12": [
  spec("bag", 0.12, 0.18, 0.02, "other"), spec("tube", 0.018, 0.07, 0.018, "other"),
  spec("box", 0.07, 0.18, 0.015, "other"), spec("box", 0.09, 0.13, 0.02, "other"),
  spec("box", 0.16, 0.07, 0.1, "other"), spec("bottle", 0.1, 0.2, 0.07, "other"),
  spec("bag", 0.12, 0.1, 0.06, "other"), spec("box", 0.07, 0.1, 0.015, "other"),
  spec("bag", 0.065, 0.15, 0.01, "other"), spec("box", 0.15, 0.1, 0.035, "other"),
  spec("bottle", 0.1, 0.23, 0.07, "other"), spec("box", 0.09, 0.13, 0.08, "other"),
  spec("bag", 0.065, 0.09, 0.015, "candy"), spec("box", 0.06, 0.025, 0.045, "candy"),
  spec("box", 0.045, 0.11, 0.01, "other"), spec("box", 0.09, 0.065, 0.008, "other"),
], "starter-13": [
  spec("cup", 0.15, 0.08, 0.15, "pantry"),   spec("cup", 0.15, 0.07, 0.15, "pantry"),
  spec("cup", 0.15, 0.09, 0.15, "pantry"),   spec("box", 0.18, 0.04, 0.13, "pantry"),
  spec("box", 0.25, 0.03, 0.25, "pantry"),   spec("box", 0.25, 0.03, 0.25, "pantry"),
  spec("box", 0.17, 0.035, 0.12, "pantry"),   spec("box", 0.19, 0.04, 0.13, "pantry"),
  spec("cup", 0.17, 0.09, 0.17, "pantry"),   spec("cup", 0.17, 0.09, 0.17, "pantry"),
  spec("bag", 0.08, 0.18, 0.07, "pantry"),   spec("cup", 0.16, 0.08, 0.16, "pantry"),
  spec("box", 0.2, 0.04, 0.15, "pantry"),   spec("cup", 0.15, 0.08, 0.15, "pantry"),
  spec("bag", 0.1, 0.22, 0.07, "pantry"),   spec("cup", 0.15, 0.08, 0.15, "pantry"),
], "starter-14": [
  spec("bag", 0.1, 0.14, 0.01, "other"),   spec("box", 0.035, 0.16, 0.02, "other"),
  spec("bottle", 0.045, 0.13, 0.045, "other"),   spec("bag", 0.12, 0.09, 0.025, "other"),
  spec("bag", 0.13, 0.18, 0.025, "other"),   spec("box", 0.12, 0.2, 0.04, "other"),
  spec("tube", 0.1, 0.28, 0.1, "other"),   spec("box", 0.12, 0.24, 0.035, "other"),
  spec("bottle", 0.065, 0.21, 0.055, "other"),   spec("bottle", 0.075, 0.2, 0.055, "other"),
  spec("tube", 0.05, 0.12, 0.03, "other"),   spec("jar", 0.09, 0.13, 0.09, "other"),
  spec("tube", 0.05, 0.18, 0.035, "other"),   spec("box", 0.06, 0.065, 0.025, "other"),
  spec("bottle", 0.07, 0.21, 0.05, "other"),   spec("bottle", 0.035, 0.11, 0.035, "other"),
], "starter-15": [
  spec("box", 0.22, 0.26, 0.04, "other"),   spec("box", 0.23, 0.28, 0.06, "other"),
  spec("box", 0.12, 0.18, 0.05, "other"),   spec("box", 0.18, 0.22, 0.03, "other"),
  spec("box", 0.22, 0.12, 0.29, "other"),   spec("box", 0.21, 0.1, 0.28, "other"),
  spec("box", 0.22, 0.08, 0.27, "other"),   spec("box", 0.2, 0.08, 0.26, "other"),
  spec("pot", 0.1, 0.25, 0.1, "other"),   spec("pot", 0.2, 0.24, 0.18, "other"),
  spec("pot", 0.18, 0.27, 0.16, "other"),   spec("pot", 0.14, 0.25, 0.14, "other"),
  spec("bottle", 0.23, 0.22, 0.12, "other"),   spec("box", 0.075, 0.25, 0.035, "other"),
  spec("box", 0.07, 0.2, 0.025, "other"),   spec("box", 0.14, 0.23, 0.03, "other"),
], "starter-16": [
  spec("box", 0.08, 0.24, 0.04, "other"),   spec("bottle", 0.05, 0.16, 0.05, "other"),
  spec("bag", 0.16, 0.17, 0.02, "other"),   spec("box", 0.24, 0.3, 0.035, "other"),
  spec("bag", 0.13, 0.18, 0.1, "other"),   spec("box", 0.035, 0.18, 0.025, "other"),
  spec("tube", 0.09, 0.11, 0.09, "other"),   spec("box", 0.24, 0.22, 0.16, "other"),
  spec("tube", 0.13, 0.08, 0.08, "other"),   spec("pot", 0.12, 0.2, 0.1, "other"),
  spec("bag", 0.12, 0.2, 0.055, "other"),   spec("box", 0.16, 0.24, 0.04, "other"),
  spec("box", 0.16, 0.3, 0.12, "other"),   spec("box", 0.07, 0.1, 0.05, "other"),
  spec("box", 0.13, 0.035, 0.085, "other"),   spec("cup", 0.08, 0.11, 0.08, "other"),
], "starter-17": [
  spec("box", 0.07, 0.23, 0.07, "drink"),   spec("cup", 0.085, 0.07, 0.085, "pantry"),
  spec("box", 0.13, 0.025, 0.18, "pantry", true),   spec("box", 0.12, 0.035, 0.17, "pantry", true),
  spec("jar", 0.08, 0.12, 0.08, "pantry"),   spec("jar", 0.075, 0.11, 0.075, "pantry"),
  spec("jar", 0.075, 0.12, 0.075, "pantry"),   spec("bottle", 0.09, 0.16, 0.055, "pantry"),
  spec("bag", 0.08, 0.12, 0.015, "pantry"),   spec("bottle", 0.04, 0.1, 0.04, "pantry"),
  spec("jar", 0.06, 0.11, 0.06, "pantry"),   spec("cup", 0.13, 0.07, 0.07, "other"),
  spec("can", 0.06, 0.15, 0.06, "drink"),   spec("bottle", 0.06, 0.16, 0.06, "drink"),
  spec("bottle", 0.06, 0.16, 0.06, "drink"),   spec("bottle", 0.06, 0.17, 0.06, "drink"),
], "starter-18": [
  spec("box", 0.17, 0.07, 0.16, "other"),   spec("box", 0.1, 0.16, 0.025, "other"),
  spec("box", 0.13, 0.16, 0.035, "other"),   spec("tube", 0.09, 0.02, 0.09, "other"),
  spec("box", 0.1, 0.28, 0.02, "other"),   spec("box", 0.2, 0.035, 0.2, "other"),
  spec("tube", 0.09, 0.09, 0.09, "other"),   spec("box", 0.08, 0.23, 0.06, "other"),
  spec("box", 0.08, 0.025, 0.08, "other"),   spec("box", 0.09, 0.05, 0.02, "other"),
  spec("tube", 0.025, 0.1, 0.025, "other"),   spec("box", 0.07, 0.17, 0.015, "other"),
  spec("box", 0.148, 0.21, 0.018, "other"),   spec("box", 0.075, 0.18, 0.015, "other"),
  spec("box", 0.2, 0.02, 0.15, "other"),   spec("bag", 0.16, 0.22, 0.04, "other"),
], "starter-19": [
  spec("box", 0.05, 0.055, 0.04, "other"),   spec("box", 0.09, 0.13, 0.1, "other"),
  spec("box", 0.12, 0.02, 0.04, "other"),   spec("bag", 0.25, 0.3, 0.02, "other"),
  spec("box", 0.14, 0.14, 0.025, "other"),   spec("bag", 0.23, 0.16, 0.17, "other"),
  spec("bag", 0.2, 0.14, 0.05, "other"),   spec("bag", 0.15, 0.16, 0.05, "other"),
  spec("box", 0.065, 0.09, 0.025, "other"),   spec("box", 0.18, 0.06, 0.1, "other"),
  spec("box", 0.2, 0.04, 0.2, "other"),   spec("box", 0.09, 0.27, 0.09, "other"),
  spec("tube", 0.02, 0.14, 0.02, "other"),   spec("tube", 0.055, 0.15, 0.055, "other"),
  spec("bag", 0.1, 0.15, 0.1, "other"),   spec("box", 0.1, 0.11, 0.025, "other"),
], "starter-20": [
  spec("cup", 0.05, 0.065, 0.05, "other"),   spec("box", 0.13, 0.025, 0.15, "other"),
  spec("box", 0.12, 0.12, 0.12, "other"),   spec("tube", 0.06, 0.2, 0.06, "other"),
  spec("bag", 0.18, 0.22, 0.01, "other"),   spec("bag", 0.12, 0.2, 0.06, "other"),
  spec("box", 0.06, 0.2, 0.025, "other"),   spec("bag", 0.18, 0.24, 0.025, "other"),
  spec("box", 0.05, 0.28, 0.02, "other"),   spec("box", 0.08, 0.28, 0.07, "other"),
  spec("box", 0.075, 0.15, 0.02, "other"),   spec("box", 0.15, 0.28, 0.04, "other"),
  spec("cup", 0.12, 0.12, 0.1, "other"),   spec("box", 0.2, 0.3, 0.018, "other"),
  spec("box", 0.055, 0.18, 0.035, "other"),   spec("box", 0.04, 0.15, 0.04, "other"),
], "starter-21": [
  spec("box", 0.22, 0.06, 0.18, "other"),    spec("bag", 0.24, 0.14, 0.2, "other"),
  spec("box", 0.26, 0.025, 0.26, "other"),    spec("cup", 0.16, 0.08, 0.16, "other"),
  spec("box", 0.17, 0.07, 0.12, "other"),    spec("bag", 0.16, 0.2, 0.025, "other"),
  spec("box", 0.07, 0.22, 0.04, "other"),    spec("box", 0.08, 0.16, 0.025, "other"),
  spec("bag", 0.12, 0.12, 0.04, "other"),    spec("box", 0.1, 0.055, 0.04, "other"),
  spec("box", 0.15, 0.02, 0.2, "other"),    spec("bag", 0.1, 0.22, 0.025, "other"),
  spec("box", 0.16, 0.055, 0.11, "other"),    spec("bag", 0.1, 0.23, 0.025, "other"),
  spec("tube", 0.06, 0.28, 0.06, "other"),    spec("tube", 0.09, 0.08, 0.09, "other"),
], "starter-22": [
  spec("box", 0.14, 0.055, 0.1, "other"),    spec("bottle", 0.075, 0.24, 0.075, "other"),
  spec("box", 0.12, 0.025, 0.18, "other"),    spec("box", 0.16, 0.06, 0.07, "other"),
  spec("box", 0.17, 0.04, 0.2, "other"),    spec("box", 0.13, 0.15, 0.035, "other"),
  spec("box", 0.12, 0.045, 0.12, "other"),    spec("box", 0.13, 0.045, 0.27, "other"),
  spec("bag", 0.22, 0.035, 0.22, "other"),    spec("cup", 0.1, 0.11, 0.08, "other"),
  spec("bag", 0.24, 0.14, 0.2, "other"),    spec("box", 0.16, 0.28, 0.16, "other"),
  spec("box", 0.14, 0.025, 0.14, "other"),    spec("box", 0.06, 0.15, 0.035, "other"),
  spec("cup", 0.12, 0.09, 0.1, "other"),    spec("box", 0.05, 0.27, 0.05, "other"),
], "starter-23": [
  spec("box", 0.08, 0.07, 0.035, "other"),    spec("box", 0.16, 0.06, 0.07, "other"),
  spec("box", 0.16, 0.22, 0.1, "other"),    spec("box", 0.28, 0.055, 0.025, "other"),
  spec("bottle", 0.06, 0.19, 0.06, "other"),    spec("bag", 0.14, 0.22, 0.035, "other"),
  spec("tube", 0.1, 0.045, 0.1, "other"),    spec("box", 0.1, 0.14, 0.04, "other"),
  spec("tube", 0.22, 0.035, 0.22, "other"),    spec("box", 0.05, 0.09, 0.055, "other"),
  spec("bag", 0.1, 0.16, 0.04, "other"),    spec("box", 0.09, 0.07, 0.18, "other"),
  spec("bag", 0.25, 0.3, 0.12, "other"),    spec("box", 0.26, 0.07, 0.18, "other"),
  spec("pot", 0.2, 0.18, 0.2, "other"),    spec("box", 0.12, 0.2, 0.06, "other"),
], "starter-24": [
  spec("bag", 0.13, 0.2, 0.05, "pantry"),    spec("jar", 0.085, 0.14, 0.085, "pantry"),
  spec("jar", 0.075, 0.11, 0.075, "pantry"),    spec("jar", 0.08, 0.14, 0.08, "pantry"),
  spec("bag", 0.14, 0.25, 0.04, "pantry"),    spec("bottle", 0.045, 0.18, 0.045, "pantry"),
  spec("box", 0.11, 0.09, 0.08, "pantry"),    spec("bag", 0.12, 0.19, 0.04, "pantry"),
  spec("bag", 0.15, 0.24, 0.06, "pantry"),    spec("bottle", 0.06, 0.21, 0.06, "pantry"),
  spec("bag", 0.14, 0.2, 0.05, "pantry"),    spec("bag", 0.14, 0.2, 0.05, "pantry"),
  spec("jar", 0.05, 0.105, 0.05, "pantry"),    spec("jar", 0.05, 0.105, 0.05, "pantry"),
  spec("jar", 0.05, 0.105, 0.05, "pantry"),    spec("bag", 0.07, 0.14, 0.025, "pantry"),
], "starter-25": [
  spec("bag", 0.18, 0.11, 0.14, "produce"),    spec("bag", 0.18, 0.2, 0.12, "produce"),
  spec("box", 0.14, 0.08, 0.11, "pantry", true),    spec("box", 0.2, 0.09, 0.14, "produce"),
  spec("bag", 0.23, 0.065, 0.09, "bakery"),    spec("box", 0.12, 0.065, 0.12, "bakery"),
  spec("box", 0.12, 0.065, 0.11, "bakery"),    spec("box", 0.09, 0.035, 0.09, "bakery"),
  spec("box", 0.055, 0.11, 0.045, "drink"),    spec("bottle", 0.06, 0.12, 0.06, "drink"),
  spec("bottle", 0.06, 0.12, 0.06, "drink"),    spec("bottle", 0.06, 0.12, 0.06, "drink"),
  spec("bag", 0.1, 0.1, 0.035, "pantry", true),    spec("box", 0.12, 0.13, 0.06, "pantry", true),
  spec("bag", 0.1, 0.14, 0.06, "pantry", true),    spec("cup", 0.11, 0.105, 0.11, "pantry"),
], "starter-26": [
  spec("bottle", 0.07, 0.22, 0.05, "other"),    spec("tube", 0.06, 0.17, 0.04, "other"),
  spec("jar", 0.075, 0.07, 0.075, "other"),    spec("bag", 0.16, 0.08, 0.14, "other"),
  spec("tube", 0.06, 0.12, 0.06, "other"),    spec("box", 0.08, 0.04, 0.07, "other"),
  spec("box", 0.08, 0.04, 0.07, "other"),    spec("box", 0.09, 0.04, 0.045, "other"),
  spec("bottle", 0.07, 0.21, 0.055, "other"),    spec("box", 0.075, 0.18, 0.015, "other"),
  spec("box", 0.2, 0.035, 0.045, "other"),    spec("box", 0.09, 0.16, 0.02, "other"),
  spec("box", 0.11, 0.04, 0.09, "other"),    spec("box", 0.045, 0.2, 0.015, "other"),
  spec("bag", 0.2, 0.08, 0.16, "other"),    spec("bag", 0.18, 0.07, 0.11, "other"),
], "starter-27": [
  spec("cup", 0.12, 0.065, 0.12, "other"),    spec("box", 0.2, 0.03, 0.2, "other"),
  spec("bag", 0.2, 0.09, 0.18, "other"),    spec("box", 0.25, 0.01, 0.2, "other"),
  spec("box", 0.18, 0.11, 0.08, "other"),    spec("box", 0.11, 0.06, 0.05, "other"),
  spec("bag", 0.15, 0.2, 0.12, "other"),    spec("bag", 0.14, 0.25, 0.12, "other"),
  spec("box", 0.15, 0.15, 0.15, "other"),    spec("box", 0.1, 0.14, 0.025, "other"),
  spec("box", 0.25, 0.06, 0.18, "other"),    spec("box", 0.15, 0.025, 0.15, "other"),
  spec("box", 0.07, 0.13, 0.02, "other"),    spec("box", 0.21, 0.297, 0.003, "other"),
  spec("bag", 0.07, 0.2, 0.02, "other"),    spec("box", 0.16, 0.08, 0.06, "other"),
], "starter-28": [
  spec("box", 0.18, 0.24, 0.035, "other"),    spec("box", 0.16, 0.07, 0.12, "other"),
  spec("cup", 0.12, 0.12, 0.09, "other"),    spec("bag", 0.16, 0.07, 0.14, "other"),
  spec("box", 0.18, 0.09, 0.07, "other"),    spec("box", 0.16, 0.1, 0.08, "other"),
  spec("bag", 0.14, 0.2, 0.12, "other"),    spec("bag", 0.18, 0.25, 0.12, "other"),
  spec("box", 0.23, 0.2, 0.07, "other"),    spec("box", 0.22, 0.1, 0.16, "other"),
  spec("box", 0.23, 0.05, 0.16, "other"),    spec("box", 0.25, 0.06, 0.2, "other"),
  spec("box", 0.05, 0.14, 0.015, "other"),    spec("bag", 0.08, 0.18, 0.015, "other"),
  spec("tube", 0.055, 0.1, 0.055, "other"),    spec("box", 0.17, 0.035, 0.12, "other"),
], "starter-29": [
  spec("jar", 0.09, 0.13, 0.09, "other"),    spec("box", 0.1, 0.16, 0.025, "other"),
  spec("box", 0.19, 0.04, 0.13, "other"),    spec("cup", 0.09, 0.15, 0.09, "other"),
  spec("bag", 0.1, 0.16, 0.04, "other"),    spec("bag", 0.18, 0.06, 0.15, "other"),
  spec("box", 0.15, 0.035, 0.05, "other"),    spec("bottle", 0.07, 0.17, 0.07, "other"),
  spec("box", 0.16, 0.08, 0.12, "other"),    spec("box", 0.15, 0.08, 0.08, "other"),
  spec("bag", 0.18, 0.04, 0.15, "other"),    spec("box", 0.11, 0.035, 0.07, "other"),
  spec("bag", 0.13, 0.08, 0.08, "other"),    spec("box", 0.24, 0.07, 0.18, "other"),
  spec("box", 0.22, 0.05, 0.16, "other"),    spec("bag", 0.19, 0.08, 0.16, "other"),
], "starter-30": [
  spec("box", 0.14, 0.06, 0.07, "other"),    spec("box", 0.22, 0.06, 0.06, "other"),
  spec("box", 0.2, 0.08, 0.07, "other"),    spec("box", 0.18, 0.06, 0.16, "other"),
  spec("box", 0.18, 0.09, 0.12, "other"),    spec("box", 0.13, 0.17, 0.06, "other"),
  spec("box", 0.22, 0.04, 0.16, "other"),    spec("box", 0.18, 0.07, 0.12, "other"),
  spec("bag", 0.2, 0.1, 0.11, "other"),    spec("bag", 0.12, 0.18, 0.12, "other"),
  spec("bag", 0.16, 0.22, 0.13, "other"),    spec("bag", 0.18, 0.12, 0.18, "other"),
  spec("bag", 0.15, 0.1, 0.11, "other"),    spec("bag", 0.3, 0.11, 0.14, "other"),
  spec("bag", 0.15, 0.25, 0.11, "other"),    spec("bag", 0.15, 0.08, 0.12, "other"),
], "starter-31": [
  spec("box", 0.22, 0.025, 0.22, "other"),    spec("box", 0.18, 0.045, 0.13, "other"),
  spec("box", 0.12, 0.035, 0.09, "other"),    spec("box", 0.18, 0.04, 0.13, "other"),
  spec("box", 0.2, 0.1, 0.04, "other"),    spec("box", 0.23, 0.025, 0.15, "other"),
  spec("box", 0.2, 0.025, 0.2, "other"),    spec("box", 0.2, 0.05, 0.15, "other"),
  spec("box", 0.07, 0.07, 0.07, "other"),    spec("box", 0.16, 0.03, 0.12, "other"),
  spec("box", 0.09, 0.015, 0.09, "other"),    spec("box", 0.15, 0.035, 0.11, "other"),
  spec("box", 0.2, 0.03, 0.2, "other"),    spec("box", 0.16, 0.04, 0.12, "other"),
  spec("box", 0.2, 0.08, 0.15, "other"),    spec("box", 0.22, 0.09, 0.09, "other"),
], "starter-32": [
  spec("bottle", 0.04, 0.11, 0.04, "other"),    spec("box", 0.16, 0.035, 0.1, "other"),
  spec("box", 0.025, 0.17, 0.015, "other"),    spec("box", 0.11, 0.04, 0.08, "other"),
  spec("box", 0.15, 0.02, 0.15, "other"),    spec("box", 0.15, 0.15, 0.1, "other"),
  spec("box", 0.11, 0.18, 0.02, "other"),    spec("box", 0.18, 0.12, 0.1, "other"),
  spec("box", 0.07, 0.15, 0.025, "other"),    spec("bottle", 0.045, 0.1, 0.045, "other"),
  spec("bottle", 0.045, 0.1, 0.045, "other"),    spec("bag", 0.1, 0.13, 0.035, "other"),
  spec("bag", 0.11, 0.15, 0.025, "other"),    spec("jar", 0.05, 0.06, 0.05, "other"),
  spec("box", 0.12, 0.08, 0.07, "other"),    spec("cup", 0.085, 0.09, 0.085, "other"),
], "starter-33": [
  spec("bottle", 0.068, 0.22, 0.068, "drink"),    spec("bottle", 0.11, 0.32, 0.11, "drink"),
  spec("bottle", 0.075, 0.24, 0.075, "drink"),    spec("bottle", 0.075, 0.24, 0.075, "drink"),
  spec("bottle", 0.07, 0.21, 0.07, "drink"),    spec("can", 0.06, 0.145, 0.06, "drink"),
  spec("bottle", 0.068, 0.23, 0.068, "drink"),    spec("bottle", 0.085, 0.28, 0.085, "drink"),
  spec("can", 0.053, 0.135, 0.053, "drink"),    spec("can", 0.065, 0.16, 0.065, "drink"),
  spec("bottle", 0.06, 0.17, 0.06, "drink"),    spec("bottle", 0.065, 0.18, 0.065, "drink"),
  spec("can", 0.055, 0.1, 0.055, "drink"),    spec("bottle", 0.065, 0.18, 0.065, "drink"),
  spec("bottle", 0.065, 0.18, 0.065, "drink"),    spec("bottle", 0.065, 0.19, 0.065, "drink"),
], "starter-34": [
  spec("can", 0.066, 0.168, 0.066, "drink"),    spec("box", 0.14, 0.125, 0.14, "drink"),
  spec("can", 0.066, 0.168, 0.066, "drink"),    spec("can", 0.066, 0.168, 0.066, "drink"),
  spec("bottle", 0.063, 0.2, 0.063, "drink"),    spec("bottle", 0.063, 0.2, 0.063, "drink"),
  spec("bottle", 0.085, 0.25, 0.085, "drink"),    spec("can", 0.066, 0.17, 0.066, "drink"),
  spec("bottle", 0.075, 0.3, 0.075, "drink"),    spec("can", 0.066, 0.12, 0.066, "drink"),
  spec("bottle", 0.068, 0.21, 0.068, "drink"),    spec("bottle", 0.068, 0.21, 0.068, "drink"),
  spec("can", 0.066, 0.12, 0.066, "drink"),    spec("can", 0.066, 0.12, 0.066, "drink"),
  spec("can", 0.066, 0.12, 0.066, "drink"),    spec("bottle", 0.07, 0.23, 0.07, "drink"),
], "starter-35": [
  spec("box", 0.07, 0.18, 0.07, "icecream"),    spec("bag", 0.06, 0.18, 0.025, "icecream", true),
  spec("bag", 0.15, 0.09, 0.035, "icecream", true),    spec("bag", 0.06, 0.18, 0.025, "icecream", true),
  spec("box", 0.12, 0.04, 0.09, "icecream", true),    spec("pint", 0.1, 0.11, 0.1, "icecream"),
  spec("box", 0.12, 0.04, 0.08, "icecream", true),    spec("cup", 0.1, 0.095, 0.1, "icecream"),
  spec("cup", 0.09, 0.075, 0.09, "icecream"),    spec("bag", 0.19, 0.24, 0.07, "frozen", true),
  spec("box", 0.19, 0.04, 0.15, "frozen", true),    spec("box", 0.075, 0.19, 0.075, "icecream"),
  spec("box", 0.075, 0.19, 0.075, "icecream"),    spec("cup", 0.09, 0.075, 0.09, "icecream"),
  spec("cup", 0.09, 0.075, 0.09, "icecream"),    spec("cup", 0.09, 0.075, 0.09, "icecream"),
], "starter-36": [
  spec("bottle", 0.07, 0.19, 0.07, "drink"),    spec("bottle", 0.04, 0.1, 0.04, "drink"),
  spec("bottle", 0.07, 0.23, 0.07, "drink"),    spec("bottle", 0.1, 0.31, 0.1, "drink"),
  spec("bottle", 0.1, 0.31, 0.1, "drink"),    spec("can", 0.066, 0.12, 0.066, "drink"),
  spec("bottle", 0.068, 0.22, 0.068, "drink"),    spec("bottle", 0.068, 0.22, 0.068, "drink"),
  spec("bottle", 0.068, 0.22, 0.068, "drink"),    spec("bottle", 0.068, 0.22, 0.068, "drink"),
  spec("bottle", 0.068, 0.22, 0.068, "drink"),    spec("cup", 0.09, 0.075, 0.09, "icecream"),
  spec("cup", 0.11, 0.14, 0.11, "icecream"),    spec("box", 0.22, 0.08, 0.1, "icecream"),
  spec("cup", 0.09, 0.2, 0.09, "drink"),    spec("cup", 0.09, 0.2, 0.09, "drink"),
], "starter-37": [
  spec("bag", 0.12, 0.18, 0.045, "pantry"),    spec("cup", 0.18, 0.14, 0.14, "drink"),
  spec("cup", 0.105, 0.1, 0.105, "drink"),    spec("cup", 0.105, 0.1, 0.105, "drink"),
  spec("cup", 0.11, 0.12, 0.11, "drink"),    spec("teaCup", 0.085, 0.16, 0.085, "drink"),
  spec("box", 0.11, 0.025, 0.11, "bakery"),    spec("box", 0.22, 0.06, 0.16, "pantry"),
  spec("cup", 0.09, 0.065, 0.09, "other"),    spec("cup", 0.105, 0.1, 0.105, "drink"),
  spec("cup", 0.105, 0.1, 0.105, "drink"),    spec("burgerBun", 0.12, 0.1, 0.12, "pantry"),
  spec("burgerBun", 0.12, 0.14, 0.12, "pantry"),    spec("burgerBun", 0.12, 0.1, 0.12, "pantry"),
  spec("burgerBun", 0.12, 0.1, 0.12, "pantry"),    spec("burgerBun", 0.12, 0.1, 0.12, "pantry"),
], "starter-38": [
  spec("burgerBun", 0.12, 0.1, 0.12, "pantry"),    spec("burgerBun", 0.08, 0.075, 0.08, "pantry"),
  spec("box", 0.12, 0.06, 0.1, "pantry"),    spec("box", 0.12, 0.06, 0.1, "pantry"),
  spec("box", 0.14, 0.06, 0.12, "pantry"),    spec("box", 0.26, 0.15, 0.18, "pantry"),
  spec("cup", 0.16, 0.075, 0.16, "noodle"),    spec("cup", 0.16, 0.075, 0.16, "noodle"),
  spec("cup", 0.16, 0.075, 0.16, "noodle"),    spec("cup", 0.16, 0.075, 0.16, "noodle"),
  spec("box", 0.18, 0.045, 0.16, "noodle"),    spec("cup", 0.16, 0.075, 0.16, "noodle"),
  spec("cup", 0.16, 0.075, 0.16, "noodle"),    spec("box", 0.18, 0.04, 0.14, "pantry"),
  spec("cup", 0.1, 0.065, 0.1, "pantry"),    spec("box", 0.26, 0.08, 0.18, "noodle"),
], "starter-39": [
  spec("cup", 0.16, 0.075, 0.16, "pantry"),    spec("box", 0.19, 0.045, 0.19, "pantry"),
  spec("cup", 0.14, 0.075, 0.14, "pantry"),    spec("cup", 0.16, 0.075, 0.16, "produce"),
  spec("box", 0.16, 0.06, 0.14, "pantry"),    spec("box", 0.18, 0.06, 0.14, "pantry"),
  spec("box", 0.28, 0.09, 0.22, "pantry"),    spec("box", 0.12, 0.04, 0.09, "pantry"),
  spec("box", 0.16, 0.04, 0.12, "pantry"),    spec("box", 0.19, 0.04, 0.14, "pantry"),
  spec("box", 0.2, 0.05, 0.15, "pantry"),    spec("box", 0.21, 0.05, 0.15, "pantry"),
  spec("cup", 0.16, 0.075, 0.16, "pantry"),    spec("cup", 0.095, 0.1, 0.095, "pantry"),
  spec("cup", 0.095, 0.1, 0.095, "produce"),    spec("cup", 0.1, 0.055, 0.1, "produce"),
], "starter-40": [
  spec("teaCup", 0.095, 0.19, 0.095, "drink"),    spec("teaCup", 0.095, 0.19, 0.095, "drink"),
  spec("teaCup", 0.095, 0.19, 0.095, "drink"),    spec("teaCup", 0.095, 0.19, 0.095, "drink"),
  spec("teaCup", 0.095, 0.19, 0.095, "drink"),    spec("teaCup", 0.095, 0.19, 0.095, "drink"),
  spec("teaCup", 0.095, 0.19, 0.095, "drink"),    spec("teaCup", 0.095, 0.19, 0.095, "drink"),
  spec("teaCup", 0.095, 0.19, 0.095, "drink"),    spec("teaCup", 0.095, 0.19, 0.095, "drink"),
  spec("box", 0.24, 0.14, 0.09, "drink"),    spec("bag", 0.08, 0.16, 0.055, "pantry"),
  spec("box", 0.22, 0.055, 0.18, "pantry"),    spec("box", 0.2, 0.035, 0.15, "pantry"),
  spec("box", 0.25, 0.04, 0.12, "pantry"),    spec("cup", 0.095, 0.1, 0.095, "pantry"),
], "starter-41": [
  spec("box", 0.22, 0.075, 0.1, "icecream"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("box", 0.14, 0.05, 0.14, "bakery"),    spec("box", 0.16, 0.04, 0.16, "bakery"),
  spec("cup", 0.065, 0.07, 0.065, "drink"),    spec("cup", 0.065, 0.105, 0.065, "drink"),
  spec("cup", 0.08, 0.12, 0.08, "drink"),    spec("box", 0.24, 0.045, 0.24, "pantry"),
  spec("box", 0.24, 0.045, 0.24, "pantry"),    spec("box", 0.24, 0.045, 0.24, "pantry"),
  spec("box", 0.17, 0.045, 0.15, "pantry"),    spec("box", 0.17, 0.045, 0.15, "pantry"),
  spec("cup", 0.12, 0.06, 0.12, "produce"),    spec("box", 0.16, 0.04, 0.16, "produce"),
  spec("box", 0.28, 0.15, 0.2, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
], "starter-42": [
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "produce"),    spec("cup", 0.15, 0.075, 0.15, "produce"),
  spec("cup", 0.12, 0.075, 0.12, "pantry"),    spec("box", 0.16, 0.045, 0.16, "produce"),
  spec("bag", 0.09, 0.07, 0.09, "bakery"),    spec("box", 0.25, 0.08, 0.18, "pantry"),
  spec("teaCup", 0.09, 0.16, 0.09, "drink"),    spec("teaCup", 0.09, 0.16, 0.09, "drink"),
  spec("teaCup", 0.09, 0.16, 0.09, "drink"),    spec("teaCup", 0.09, 0.16, 0.09, "drink"),
  spec("teaCup", 0.09, 0.16, 0.09, "drink"),    spec("teaCup", 0.09, 0.16, 0.09, "drink"),
], "starter-43": [
  spec("teaCup", 0.09, 0.16, 0.09, "drink"),    spec("teaCup", 0.09, 0.16, 0.09, "drink"),
  spec("teaCup", 0.09, 0.16, 0.09, "drink"),    spec("cup", 0.09, 0.1, 0.09, "produce"),
  spec("cup", 0.14, 0.075, 0.14, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("box", 0.2, 0.035, 0.16, "bakery"),
  spec("box", 0.15, 0.07, 0.12, "pantry"),    spec("cup", 0.09, 0.055, 0.09, "pantry"),
  spec("cup", 0.085, 0.16, 0.085, "drink"),    spec("cup", 0.085, 0.1, 0.085, "drink"),
  spec("cup", 0.1, 0.06, 0.1, "bakery"),    spec("cup", 0.16, 0.075, 0.16, "noodle"),
], "starter-44": [
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("cup", 0.1, 0.1, 0.1, "pantry"),
  spec("box", 0.18, 0.055, 0.13, "pantry"),    spec("box", 0.22, 0.06, 0.17, "pantry"),
  spec("box", 0.18, 0.05, 0.18, "bakery"),    spec("teaCup", 0.09, 0.16, 0.09, "drink"),
  spec("teaCup", 0.09, 0.16, 0.09, "drink"),    spec("bag", 0.1, 0.16, 0.06, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("box", 0.22, 0.1, 0.16, "pantry"),
  spec("box", 0.22, 0.1, 0.16, "pantry"),    spec("box", 0.2, 0.045, 0.2, "pantry"),
  spec("box", 0.2, 0.045, 0.2, "pantry"),    spec("box", 0.22, 0.07, 0.22, "pantry"),
], "starter-45": [
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("cup", 0.15, 0.09, 0.15, "pantry"),
  spec("cup", 0.17, 0.08, 0.17, "noodle"),    spec("box", 0.21, 0.045, 0.13, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("box", 0.2, 0.045, 0.2, "pantry"),
  spec("box", 0.24, 0.045, 0.17, "pantry"),    spec("box", 0.17, 0.1, 0.13, "pantry"),
  spec("box", 0.17, 0.1, 0.13, "pantry"),    spec("box", 0.22, 0.045, 0.16, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "produce"),    spec("cup", 0.15, 0.075, 0.15, "produce"),
  spec("cup", 0.15, 0.075, 0.15, "pantry"),    spec("box", 0.24, 0.045, 0.24, "pantry"),
  spec("box", 0.18, 0.045, 0.14, "pantry"),    spec("cup", 0.1, 0.055, 0.1, "produce"),
], "starter-46": [
  spec("box", 0.14, 0.05, 0.11, "bakery"),    spec("box", 0.21, 0.045, 0.17, "pantry"),
  spec("cup", 0.1, 0.06, 0.1, "produce"),    spec("box", 0.17, 0.06, 0.12, "bakery"),
  spec("cup", 0.17, 0.09, 0.17, "noodle"),    spec("cup", 0.17, 0.09, 0.17, "noodle"),
  spec("box", 0.21, 0.09, 0.11, "pantry"),    spec("cup", 0.15, 0.075, 0.15, "pantry"),
  spec("cup", 0.15, 0.075, 0.15, "noodle"),    spec("box", 0.18, 0.055, 0.13, "pantry"),
  spec("box", 0.19, 0.055, 0.14, "pantry"),    spec("teaCup", 0.085, 0.14, 0.085, "drink"),
  spec("teaCup", 0.085, 0.14, 0.085, "drink"),    spec("cup", 0.09, 0.08, 0.09, "bakery"),
  spec("box", 0.12, 0.1, 0.06, "other"),    spec("jar", 0.055, 0.025, 0.055, "other"),
], "starter-47": [
  spec("jar", 0.065, 0.09, 0.065, "other"),    spec("box", 0.14, 0.2, 0.025, "other"),
  spec("box", 0.07, 0.17, 0.015, "other"),    spec("box", 0.025, 0.13, 0.01, "other"),
  spec("bag", 0.16, 0.12, 0.06, "other"),    spec("box", 0.14, 0.085, 0.07, "other"),
  spec("bottle", 0.055, 0.125, 0.055, "other"),    spec("box", 0.085, 0.075, 0.035, "other"),
  spec("bottle", 0.065, 0.12, 0.065, "other"),    spec("bottle", 0.06, 0.105, 0.06, "other"),
  spec("bottle", 0.06, 0.105, 0.06, "other"),    spec("jar", 0.12, 0.15, 0.12, "other"),
  spec("jar", 0.12, 0.15, 0.12, "other"),    spec("box", 0.11, 0.12, 0.055, "other"),
  spec("jar", 0.1, 0.125, 0.1, "other"),    spec("bottle", 0.06, 0.11, 0.06, "other"),
], "starter-48": [
  spec("bottle", 0.065, 0.125, 0.065, "other"),    spec("jar", 0.1, 0.125, 0.1, "other"),
  spec("bag", 0.11, 0.17, 0.045, "snack"),    spec("box", 0.07, 0.2, 0.03, "other"),
  spec("tube", 0.055, 0.16, 0.035, "other"),    spec("box", 0.1, 0.125, 0.04, "other"),
  spec("box", 0.07, 0.1, 0.03, "other"),    spec("box", 0.07, 0.16, 0.03, "other"),
  spec("box", 0.5, 0.8, 0.45, "other"),    spec("box", 0.1, 0.65, 0.025, "other"),
  spec("bag", 0.32, 0.22, 0.07, "other"),    spec("box", 0.16, 0.22, 0.018, "other"),
  spec("jar", 0.085, 0.12, 0.085, "other"),    spec("box", 0.15, 0.015, 0.12, "other"),
  spec("box", 0.22, 0.075, 0.16, "other"),    spec("box", 0.24, 0.17, 0.075, "other"),
], "starter-49": [
  spec("bottle", 0.06, 0.15, 0.06, "other"),    spec("box", 0.1, 0.07, 0.035, "other"),
  spec("box", 0.035, 0.19, 0.02, "other"),    spec("tube", 0.035, 0.09, 0.035, "other"),
  spec("bottle", 0.04, 0.09, 0.04, "other"),    spec("tube", 0.065, 0.18, 0.035, "other"),
  spec("bag", 0.12, 0.15, 0.015, "other"),    spec("tube", 0.045, 0.11, 0.035, "other"),
  spec("jar", 0.08, 0.08, 0.08, "other"),    spec("bottle", 0.055, 0.105, 0.055, "other"),
  spec("bottle", 0.025, 0.065, 0.025, "other"),    spec("bottle", 0.045, 0.105, 0.045, "drink"),
  spec("bag", 0.11, 0.14, 0.015, "other"),    spec("bottle", 0.065, 0.12, 0.065, "other"),
  spec("bottle", 0.06, 0.105, 0.06, "other"),    spec("box", 0.105, 0.11, 0.05, "other"),
], "starter-50": [
  spec("box", 0.17, 0.1, 0.08, "other"),    spec("tube", 0.055, 0.16, 0.035, "other"),
  spec("bottle", 0.07, 0.17, 0.07, "other"),    spec("bottle", 0.065, 0.155, 0.065, "other"),
  spec("box", 0.25, 0.035, 0.19, "other"),    spec("bag", 0.13, 0.1, 0.06, "other"),
  spec("box", 0.07, 0.22, 0.035, "other"),    spec("box", 0.13, 0.055, 0.08, "other"),
  spec("box", 0.08, 0.065, 0.08, "other"),    spec("bag", 0.15, 0.12, 0.055, "other"),
  spec("bag", 0.22, 0.32, 0.12, "other"),    spec("bag", 0.08, 0.13, 0.035, "other"),
  spec("bottle", 0.07, 0.19, 0.07, "other"),    spec("bag", 0.24, 0.34, 0.14, "other"),
  spec("box", 0.18, 0.065, 0.07, "other"),    spec("cup", 0.16, 0.065, 0.16, "other"),
], "starter-51": [
  spec("box", 0.17, 0.06, 0.13, "other"),    spec("bag", 0.28, 0.18, 0.18, "other"),
  spec("box", 0.2, 0.02, 0.18, "other"),    spec("box", 0.11, 0.22, 0.1, "other"),
  spec("box", 0.17, 0.025, 0.12, "other"),    spec("box", 0.15, 0.07, 0.08, "other"),
  spec("box", 0.05, 0.025, 0.035, "other"),    spec("box", 0.065, 0.15, 0.065, "drink"),
  spec("box", 0.18, 0.035, 0.12, "pantry"),    spec("box", 0.055, 0.1, 0.055, "pantry"),
  spec("jar", 0.08, 0.065, 0.08, "pantry"),    spec("bag", 0.13, 0.2, 0.06, "pantry"),
  spec("cup", 0.075, 0.065, 0.075, "snack"),    spec("bag", 0.12, 0.18, 0.05, "pantry"),
  spec("bag", 0.12, 0.19, 0.05, "snack"),    spec("bag", 0.1, 0.15, 0.04, "snack"),
], "starter-52": [
  spec("bag", 0.1, 0.15, 0.045, "snack"),    spec("box", 0.09, 0.035, 0.055, "snack"),
  spec("bag", 0.1, 0.15, 0.04, "snack"),    spec("bag", 0.11, 0.17, 0.05, "snack"),
  spec("box", 0.18, 0.055, 0.12, "bakery"),    spec("box", 0.13, 0.05, 0.13, "bakery"),
  spec("bag", 0.055, 0.1, 0.025, "snack"),    spec("bag", 0.1, 0.15, 0.045, "snack"),
  spec("bottle", 0.06, 0.2, 0.06, "drink"),    spec("bottle", 0.06, 0.18, 0.06, "drink"),
  spec("bottle", 0.06, 0.18, 0.06, "drink"),    spec("bottle", 0.06, 0.2, 0.06, "drink"),
  spec("bottle", 0.06, 0.2, 0.06, "drink"),    spec("bottle", 0.06, 0.18, 0.06, "drink"),
  spec("bottle", 0.065, 0.23, 0.065, "drink"),    spec("box", 0.1, 0.22, 0.025, "other"),
], "starter-53": [
  spec("bottle", 0.045, 0.11, 0.045, "drink"),    spec("box", 0.045, 0.115, 0.045, "drink"),
  spec("box", 0.07, 0.15, 0.025, "pantry"),    spec("box", 0.16, 0.08, 0.045, "drink"),
  spec("box", 0.22, 0.05, 0.16, "pantry"),    spec("box", 0.22, 0.05, 0.16, "pantry"),
  spec("cup", 0.16, 0.08, 0.16, "pantry"),    spec("box", 0.12, 0.095, 0.12, "pantry"),
  spec("box", 0.09, 0.035, 0.09, "bakery"),    spec("box", 0.12, 0.07, 0.09, "bakery"),
  spec("cup", 0.085, 0.14, 0.085, "bakery"),    spec("cup", 0.085, 0.075, 0.085, "bakery"),
  spec("box", 0.12, 0.085, 0.09, "bakery"),    spec("box", 0.085, 0.025, 0.085, "bakery"),
  spec("jar", 0.085, 0.095, 0.085, "pantry"),    spec("bag", 0.15, 0.23, 0.065, "pantry"),
], "starter-54": [
  spec("bag", 0.14, 0.21, 0.06, "pantry"),    spec("box", 0.13, 0.2, 0.06, "pantry"),
  spec("bag", 0.1, 0.16, 0.045, "pantry"),    spec("bag", 0.14, 0.22, 0.06, "pantry"),
  spec("bag", 0.12, 0.2, 0.065, "pantry"),    spec("box", 0.12, 0.08, 0.065, "pantry"),
  spec("box", 0.12, 0.08, 0.065, "pantry"),    spec("bag", 0.1, 0.17, 0.045, "pantry"),
  spec("bottle", 0.055, 0.22, 0.055, "pantry"),    spec("box", 0.14, 0.14, 0.025, "other"),
  spec("cup", 0.12, 0.1, 0.12, "other"),    spec("box", 0.06, 0.11, 0.06, "other"),
  spec("box", 0.06, 0.065, 0.045, "other"),    spec("cup", 0.065, 0.07, 0.065, "other"),
  spec("bag", 0.14, 0.2, 0.065, "pantry"),    spec("jar", 0.065, 0.085, 0.065, "pantry"),
], "starter-55": [
  spec("jar", 0.08, 0.11, 0.08, "pantry"),    spec("box", 0.095, 0.16, 0.015, "pantry"),
  spec("bag", 0.11, 0.17, 0.05, "pantry"),    spec("bag", 0.14, 0.2, 0.065, "pantry"),
  spec("box", 0.2, 0.015, 0.14, "other"),    spec("box", 0.18, 0.04, 0.13, "frozen", true),
  spec("box", 0.18, 0.04, 0.13, "frozen", true),    spec("bag", 0.15, 0.21, 0.045, "frozen", true),
  spec("bag", 0.15, 0.21, 0.045, "frozen", true),    spec("box", 0.18, 0.04, 0.13, "frozen", true),
  spec("box", 0.18, 0.04, 0.13, "frozen", true),    spec("box", 0.15, 0.055, 0.15, "frozen", true),
  spec("bag", 0.15, 0.21, 0.045, "frozen", true),    spec("bag", 0.15, 0.21, 0.045, "frozen", true),
  spec("bag", 0.15, 0.21, 0.045, "frozen", true),    spec("box", 0.22, 0.025, 0.15, "frozen", true),
], "starter-56": [
  spec("box", 0.17, 0.035, 0.12, "pantry", true),    spec("box", 0.17, 0.035, 0.12, "pantry", true),
  spec("box", 0.17, 0.035, 0.12, "pantry", true),    spec("box", 0.2, 0.055, 0.15, "pantry", true),
  spec("box", 0.17, 0.035, 0.12, "pantry", true),    spec("box", 0.18, 0.015, 0.12, "pantry", true),
  spec("box", 0.17, 0.035, 0.12, "pantry", true),    spec("cup", 0.11, 0.065, 0.11, "pantry", true),
  spec("box", 0.17, 0.035, 0.12, "pantry", true),    spec("box", 0.21, 0.035, 0.12, "pantry", true),
  spec("cup", 0.18, 0.17, 0.13, "other"),    spec("box", 0.025, 0.15, 0.025, "other"),
  spec("jar", 0.06, 0.04, 0.06, "other"),    spec("jar", 0.06, 0.025, 0.06, "other"),
  spec("box", 0.17, 0.012, 0.17, "other"),    spec("box", 0.045, 0.17, 0.02, "other"),
] };

export function classifyProduct(name: string, imageUrl?: string | null): PackageSpec {
  const bundled = imageUrl?.match(/^\/api\/catalog-images\/(starter-\d+)\/(\d+)\.webp$/);
  const known = bundled && STARTER_PACKAGES[bundled[1]!]?.[Number(bundled[2])];
  if (known) return known;
  const n = name.trim().toLowerCase();
  for (const [re, make] of RULES) {
    if (re.test(n)) return make(n);
  }
  return DEFAULT_SPEC;
}

// ---------------------------------------------------------------------------
// Colours

const PALETTE = [
  "#d62839", "#f77f00", "#fcbf49", "#2a9d8f", "#264653", "#e76f51", "#3a86ff",
  "#8338ec", "#ff006e", "#06a77d", "#1d3557", "#e63946", "#457b9d", "#f4a261",
  "#6a994e", "#bc4749", "#118ab2", "#ef476f", "#ffd166", "#073b4c", "#9b5de5",
  "#00a6a6", "#c1121f", "#5f0f40",
];

const KEYWORD_COLORS: [RegExp, string][] = [
  [/^(?:(?:metal|galvanized)\s+)?watering can\b/, "#a6aaa5"],
  [/\bcroissants?\b/, "#c88741"],
  [/^(?:terracotta|terra cotta|clay) (?:plant )?(?:pot|planter)\b/, "#b26e4e"],
  [/\bapples?\b/, "#a8342a"],
  [/\bavocados?\b/, "#344025"],
  [/water|smartwater|aquafina|dasani|evian|fiji|essentia|pure life/, "#8fc3ea"],
  [/diet|zero|sugarfree|sugar free/, "#c3c9d0"],
  [/mint/, "#53bf9d"],
  [/spicy|flamin|fuego|hot\b|buldak|kimchi|redhot|chili/, "#c8161d"],
  [/\bcola\b|coca-cola|\bcoke\b|dr pepper|pepsi/, "#a8102a"],
  [/lemon-lime|sprite|mountain dew|green tea|\bgreen\b|lime/, "#2e9443"],
  [/orange|mango|cheddar|nacho|cheez|cheese/, "#ef7d1a"],
  [/strawberry|berry|cherry|raspberry|watermelon/, "#d42f55"],
  [/chocolate|fudge|brownie|coffee|mocha|cocoa|beef|jerky|teriyaki|bbq|barbecue|steak/, "#5b3524"],
  [/blueberry|cool ranch|cool blue|\bblue\b/, "#2557b5"],
  [/peach|apricot|salmon/, "#f2a067"],
  [/caramel|honey|maple|brown sugar|peanut|butter/, "#c98a2b"],
  [/grape|purple|acai/, "#6a3d9c"],
  [/lemon|banana|yellow|mustard|corn\b/, "#efc81f"],
  [/vanilla|cream|coconut|white|salt\b|milk/, "#efe6d2"],
  [/chicken|noodle|ramen/, "#e2a531"],
  [/tea\b|matcha/, "#7a9a3a"],
];

export interface ProductPalette {
  base: string;
  accent: string;
  ink: string;
  // 0..3: label layout variation.
  style: number;
}

function parseHex(hex: string): [number, number, number] {
  const v = parseInt(hex.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

function toHex([r, g, b]: [number, number, number]): string {
  const c = (x: number) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

export function shade(hex: string, factor: number): string {
  const [r, g, b] = parseHex(hex);
  if (factor >= 0) return toHex([r + (255 - r) * factor, g + (255 - g) * factor, b + (255 - b) * factor]);
  const k = 1 + factor;
  return toHex([r * k, g * k, b * k]);
}

export function luminance(hex: string): number {
  const [r, g, b] = parseHex(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function productPalette(name: string): ProductPalette {
  const n = name.toLowerCase();
  const h = hashString(n);
  let base = PALETTE[h % PALETTE.length]!;
  for (const [re, color] of KEYWORD_COLORS) {
    if (re.test(n)) {
      base = color;
      break;
    }
  }
  const kind = classifyProduct(n).kind;
  if (kind === "onion") base = "#a26530";
  else if (kind === "kiwi") base = "#8d633b";
  else if (kind === "sweetPotato") base = "#8b594b";
  else if (kind === "asianPear") base = "#acb56a";
  else if (kind === "ginger") base = "#b49a72";
  else if (kind === "burgerBun") base = "#c9944f";
  // Per-product jitter so same-keyword products are distinguishable.
  base = shade(base, (hash01(n, 7) - 0.5) * 0.24);
  let accent = PALETTE[(h >>> 8) % PALETTE.length]!;
  if (accent === base) accent = PALETTE[(h >>> 12) % PALETTE.length]!;
  const ink = luminance(base) > 0.42 ? "#1b1d22" : "#ffffff";
  return { base, accent, ink, style: (h >>> 4) % 4 };
}

// ---------------------------------------------------------------------------
// Label text

export interface LabelText {
  brand: string;
  detail: string;
  size: string;
}

const SIZE_RE = /\s*(\d+(?:\.\d+)?\s?(?:fl oz|oz|ml|l|liter|litre|g|kg|ct|pack|-pack)|\d+-pack|\d+ct|1 liter)$/i;

export function splitLabel(name: string): LabelText {
  let rest = name.trim();
  let size = "";
  const m = rest.match(SIZE_RE);
  if (m && m.index !== undefined && m.index > 0) {
    size = m[1]!.trim();
    rest = rest.slice(0, m.index).trim();
  }
  const words = rest.split(/\s+/).filter(Boolean);
  let take = 1;
  // Join short or ampersand brands: "Dr Pepper", "Ben & Jerry's", "M&M's Peanut".
  // Short first words are usually half of a two-word brand ("Red Bull", "Kit Kat",
  // "Slim Jim"); ampersands join ("Ben & Jerry's").
  if (words.length > 1 && words[0]!.length <= 5) take = 2;
  while (take < words.length && take < 3 && (words[take] === "&" || words[take - 1] === "&")) take++;
  const brand = words.slice(0, take).join(" ");
  const detail = words.slice(take).join(" ");
  return { brand, detail, size };
}
