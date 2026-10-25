"""Ready-made web shops. Each template takes categories from the app's generic product catalog (names in English
and Korean, illustrative prices, bundled photos for most products) and adds what a web shop shows: ratings, review
counts, discounts, stock, badges and weekly sales, drawn deterministically per template and seed.

A site can also be made from a physical store's shelves (`site_from_store`), so the same assortment can be studied
in the aisle and in the browser.
"""

import random
from dataclasses import dataclass, field

from store_emulator.domain.online import (
    OnlineCategory,
    OnlineProduct,
    OnlineSite,
    OnlineTemplate,
    ProductBadge,
    SiteOptions,
    TemplateHighlight,
)
from store_emulator.domain.store import Store
from store_emulator.domain.types import stable_seed
from store_emulator.engine.layout_gen.catalog import CATALOG, CATEGORY_LABELS, CatalogItem, localized
from store_emulator.engine.layout_gen.catalog_expansion import PACKSHOT_URLS
from store_emulator.engine.perception import category_label

_PRODUCTS_PER_CATEGORY = 12
_KRW_PER_USD = 1350
_ECO_WORDS = ("reusable", "bamboo", "refill", "organic", "recycled", "plant", "compostable", "zero waste", "natural")


@dataclass(frozen=True)
class _Template:
    id: str
    name: str
    vertical: str
    tagline: str
    description: str
    categories: tuple[str, ...]
    options: SiteOptions = field(default_factory=SiteOptions)
    discount_share: float = 0.22  # products on sale


def _o(**changes: object) -> SiteOptions:
    """Template defaults: the plain options with these changes."""
    return SiteOptions.model_validate({**SiteOptions().model_dump(), **changes})


TEMPLATES: tuple[_Template, ...] = (
    _Template("grocery_delivery", "FreshCart", "grocery", "Groceries at your door in two hours",
              "Weekly grocery shop: produce, dairy, bakery, seafood, pantry and frozen food.",
              ("fresh_produce", "dairy", "bakery", "fresh_seafood", "pantry", "frozen_meals", "soft_drinks", "chips"),
              _o(theme_color="#16a34a", free_shipping_threshold=4000, home_sections=["categories", "deals", "bestsellers"],
                 quick_add=True, products_per_page=12)),
    _Template("quick_commerce", "Zoom 15", "quick_commerce", "Snacks and essentials in 15 minutes",
              "Instant delivery app: drinks, snacks, ice cream, noodles and household basics.",
              ("soft_drinks", "chips", "sweets", "ice_cream", "instant_food", "household", "energy_coffee", "checkout_impulse"),
              _o(theme_color="#7c3aed", device="mobile", shipping_fee=199, free_shipping_threshold=1500, quick_add=True,
                 one_click_buy=True, urgency=True, cookie_banner=False),
              discount_share=0.3),
    _Template("convenience_online", "CornerGo", "convenience", "Your corner store, online",
              "Ready meals, noodles, drinks, sweets and daily goods from a convenience chain.",
              ("fresh_meals", "instant_food", "soft_drinks", "sweets", "dairy", "household"),
              _o(theme_color="#0ea5e9", free_shipping_threshold=2000, shipping_fee=299)),
    _Template("pharmacy", "CareWell Pharmacy", "pharmacy", "Health and care essentials",
              "Over-the-counter care, vitamins, first aid, oral care and home-care supplies.",
              ("pharmacy_care", "wellness", "nutrition_supplements", "first_aid_tools", "oral_care", "care_supplies"),
              _o(theme_color="#0d9488", trust_badges=True, recommendations="similar", return_policy="free_30")),
    _Template("beauty", "Glow Room", "beauty", "Skincare, makeup and self-care",
              "Facial skincare, makeup tools, hair care, nail care, bath and body, fragrances.",
              ("facial_skincare", "makeup_accessories", "hair_care", "nail_grooming", "bath_body", "fragrances"),
              _o(theme_color="#db2777", welcome_popup="coupon", coupon_code="GLOW10", coupon_percent=10, coupon_public=False,
                 social_proof=True, home_sections=["bestsellers", "new", "deals"])),
    _Template("mens_grooming", "Sharp & Co", "grooming", "Grooming done right",
              "Shaving, hair, oral and body care and fragrances for men.",
              ("shaving_grooming", "hair_care", "oral_care", "bath_body", "fragrances"),
              _o(theme_color="#334155", grid_columns=3)),
    _Template("pet_store", "Happy Paws", "pets", "Everything for cats, dogs and small friends",
              "Food, toys, grooming, walking gear and supplies for small pets, birds and fish.",
              ("pet_care", "pet_accessories", "pet_enrichment", "pet_grooming", "pet_walking", "small_pet_supplies",
               "bird_supplies", "aquarium_supplies"),
              _o(theme_color="#ea580c", recommendations="similar", free_shipping_threshold=3000)),
    _Template("baby_store", "Little Sprout", "baby", "Gentle things for little ones",
              "Diapers, baby care, feeding, bath time, plush and learning toys.",
              ("baby_supplies", "baby_care", "baby_feeding", "baby_bath", "plush_toys", "educational_toys"),
              _o(theme_color="#f59e0b", trust_badges=True, return_policy="free_30")),
    _Template("toy_store", "Toybox Planet", "toys", "Play, build and learn",
              "Toys, vehicles, plush, educational toys, puzzles and board games.",
              ("toys_hobbies", "toy_vehicles", "plush_toys", "educational_toys", "puzzle_games", "tabletop_games"),
              _o(theme_color="#e11d48", home_sections=["categories", "bestsellers", "new"])),
    _Template("hobby_models", "Model Bench", "hobby", "Kits, paints and tools for makers",
              "Model building tools, miniature painting, board games, puzzles and craft kits.",
              ("model_building_supplies", "miniature_painting", "tabletop_games", "puzzle_games", "art_craft"),
              _o(theme_color="#4f46e5", grid_columns=3)),
    _Template("art_supplies", "Inkwell Art", "art", "Supplies for every medium",
              "Fine art supplies, craft kits, stationery, desk organisers and textiles.",
              ("fine_art_supplies", "art_craft", "stationery", "desk_organization", "sewing_textiles"),
              _o(theme_color="#9333ea")),
    _Template("craft_maker", "Maker Loft", "craft", "Make it by hand",
              "Leathercraft, woodcraft, ceramics, sewing, candles and gift wrapping.",
              ("leathercraft", "woodcraft_supplies", "ceramic_craft_supplies", "sewing_textiles", "candle_care",
               "gift_wrapping"),
              _o(theme_color="#a16207")),
    _Template("stationery", "Paper & Pen", "stationery", "Write, plan and organise",
              "Stationery, desk organisation, books and gift wrapping.",
              ("stationery", "desk_organization", "books", "gift_wrapping"),
              _o(theme_color="#0f766e", free_shipping_threshold=2500)),
    _Template("bookstore", "Paper Lantern Books", "books", "Stories, games and gifts",
              "Books, board games, puzzles and stationery.",
              ("books", "tabletop_games", "puzzle_games", "stationery"),
              _o(theme_color="#78350f", recommendations="popular", reviews_on_product=True)),
    _Template("electronics", "Voltmart", "electronics", "Gadgets and accessories",
              "Electronics, digital accessories, computer peripherals, camera gear and lighting.",
              ("electronics", "digital_accessories", "computer_peripherals", "photography_accessories", "home_lighting"),
              _o(theme_color="#1d4ed8", payment_methods=["card", "paypal", "apple_pay", "bnpl"],
                 preselected_addon_percent=12, return_policy="paid")),
    _Template("home_kitchen", "Copper & Oak", "kitchen", "Cook, bake and serve",
              "Kitchen tools, dinnerware, food storage, barista tools, bakeware and tea brewing.",
              ("kitchen_tools", "dinnerware", "food_storage", "barista_tools", "baking_equipment", "tea_brewing_tools"),
              _o(theme_color="#b45309")),
    _Template("home_decor", "Nestwell", "home", "Make your home yours",
              "Home design, lighting, linen, candles, indoor plants and bathroom accessories.",
              ("home_design", "home_lighting", "home_linen", "candle_care", "indoor_plants", "bathroom_accessories"),
              _o(theme_color="#57534e", grid_columns=3, hero_text="New season, new home")),
    _Template("home_organization", "Tidy Nest", "organization", "A place for everything",
              "Storage boxes, pantry and desk organisers, laundry and zero-waste cleaning.",
              ("home_storage", "pantry_organization", "desk_organization", "laundry_care", "zero_waste_cleaning",
               "bathroom_accessories"),
              _o(theme_color="#0891b2")),
    _Template("cleaning_supplies", "Spotless", "cleaning", "Clean home, less waste",
              "Household basics, laundry care, refills and zero-waste cleaning.",
              ("household", "laundry_care", "zero_waste_cleaning", "refill_goods"),
              _o(theme_color="#2563eb", quick_add=True)),
    _Template("garden_center", "Green Thumb", "garden", "Grow something beautiful",
              "Garden supplies, indoor plants, seed starting, propagation and flowers.",
              ("garden_supplies", "indoor_plants", "seed_starting", "plant_propagation", "flowers"),
              _o(theme_color="#15803d")),
    _Template("florist", "Bloom Post", "flowers", "Flowers and gifts, delivered",
              "Bouquets, plants, sweets, gift wrap and candles for every occasion.",
              ("flowers", "indoor_plants", "gift_confectionery", "gift_wrapping", "candle_care"),
              _o(theme_color="#be185d", urgency=True, hero_text="Order by 2 pm for same-day delivery")),
    _Template("fashion", "Threadline", "fashion", "Everyday style",
              "Apparel, footwear, hair accessories, jewellery, eyewear and shoe care.",
              ("apparel", "footwear", "hair_accessories", "jewelry", "eyewear", "shoe_care"),
              _o(theme_color="#111827", welcome_popup="newsletter", coupon_code="STYLE15", coupon_percent=15,
                 coupon_public=False, social_proof=True, sponsored_slots=1),
              discount_share=0.3),
    _Template("jewelry_accessories", "Lumen", "jewelry", "Small things that shine",
              "Jewellery, eyewear and hair accessories.",
              ("jewelry", "eyewear", "hair_accessories"),
              _o(theme_color="#a855f7", grid_columns=3, trust_badges=True, free_shipping_threshold=0)),
    _Template("sports_store", "Peak Sports", "sports", "Gear for every workout",
              "Sports, yoga and pilates, running, swimming, climbing and cycling gear.",
              ("sports", "yoga_pilates", "running_accessories", "swimming_gear", "climbing_accessories",
               "bicycle_accessories", "cycling_maintenance"),
              _o(theme_color="#dc2626")),
    _Template("outdoor_camping", "Trailhead", "outdoor", "Ready for the trail",
              "Outdoor gear, camp cooking, repairs, picnic reusables, travel gear and fishing.",
              ("outdoor_gear", "outdoor_cooking", "camp_repair", "picnic_reusables", "travel_gear", "fishing_tackle"),
              _o(theme_color="#3f6212")),
    _Template("cycling", "Spoke & Chain", "cycling", "For riders, by riders",
              "Bicycle accessories, maintenance, running accessories and sports gear.",
              ("bicycle_accessories", "cycling_maintenance", "running_accessories", "sports"),
              _o(theme_color="#ca8a04")),
    _Template("travel_shop", "Wander Pack", "travel", "Pack smarter",
              "Travel gear, travel essentials, digital accessories and souvenirs.",
              ("travel_gear", "travel_essentials", "digital_accessories", "souvenirs"),
              _o(theme_color="#0369a1")),
    _Template("music_store", "Soundcraft", "music", "Instruments and audio",
              "Music gear, digital accessories and computer peripherals.",
              ("music_gear", "digital_accessories", "computer_peripherals"),
              _o(theme_color="#7e22ce", payment_methods=["card", "paypal", "bnpl"])),
    _Template("coffee_tea", "Bean & Leaf", "coffee", "Brew better at home",
              "Coffee and tea, loose-leaf teas, barista tools and tea brewing tools.",
              ("home_coffee_tea", "tea_menu", "barista_tools", "tea_brewing_tools"),
              _o(theme_color="#7c2d12", hero_text="Fresh roast every week")),
    _Template("gourmet_pantry", "Pantry Lane", "pantry", "Flavours from around the world",
              "Mediterranean, Korean and Japanese pantry, spice blends, sauces and spreads.",
              ("mediterranean_pantry", "korean_pantry", "japanese_pantry", "spice_blends", "global_sauces",
               "breakfast_spreads"),
              _o(theme_color="#c2410c")),
    _Template("baking_shop", "Flour & Co", "baking", "Everything for bakers",
              "Baking ingredients, bakeware, cake decorating and breakfast spreads.",
              ("baking_ingredients", "baking_equipment", "baking_decorating", "breakfast_spreads"),
              _o(theme_color="#d97706")),
    _Template("plant_based", "Green Plate", "plant_based", "Plant-based, every day",
              "Plant-based foods, produce, fresh herbs and refill goods.",
              ("plant_based", "fresh_produce", "fresh_herbs", "refill_goods"),
              _o(theme_color="#65a30d")),
    _Template("snack_box", "Snack Drop", "snacks", "Treats worth sharing",
              "Artisan snacks, chips, sweets, gift confectionery and craft drinks.",
              ("artisan_snacks", "chips", "sweets", "gift_confectionery", "craft_refreshments"),
              _o(theme_color="#f97316", social_proof=True, quick_add=True)),
    _Template("beverage_shop", "Sip Supply", "beverages", "Drinks by the case",
              "Soft drinks, water and sports drinks, coffee drinks, craft drinks and juices.",
              ("soft_drinks", "water_sports", "energy_coffee", "craft_refreshments", "juice_menu"),
              _o(theme_color="#0284c7", quick_add=True)),
    _Template("liquor_store", "Cellar Door", "liquor", "Beer, wine and good company",
              "Beer and alcohol, craft drinks, cheese deli and gift confectionery.",
              ("beer_alcohol", "craft_refreshments", "cheese_deli", "gift_confectionery"),
              _o(theme_color="#881337", guest_checkout=False)),
    _Template("food_delivery", "Dinner Dash", "food_delivery", "Dinner, delivered hot",
              "Burgers, pizza, sushi, Korean, noodles, Mexican, Thai and Indian dishes.",
              ("burger_menu", "pizza_menu", "sushi_menu", "korean_menu", "noodle_menu", "mexican_menu", "thai_menu",
               "indian_menu"),
              _o(theme_color="#ef4444", device="mobile", shipping_fee=299, free_shipping_threshold=2500, service_fee=149,
                 one_click_buy=True, cookie_banner=False)),
    _Template("cafe_order", "Morning Crumb", "cafe", "Order ahead, skip the line",
              "Café drinks, bakery, desserts, bubble tea and juices for pick-up.",
              ("cafe_menu", "bakery", "desserts", "bubble_tea_menu", "juice_menu"),
              _o(theme_color="#92400e", device="mobile", shipping_fee=0, free_shipping_threshold=0, checkout_flow="one_page",
                 quick_add=True)),
    _Template("hardware_diy", "Toolhouse", "hardware", "Tools for every project",
              "Hardware, lighting, garden supplies and storage.",
              ("hardware", "home_lighting", "garden_supplies", "home_storage"),
              _o(theme_color="#ca8a04", grid_columns=3)),
    _Template("party_gifts", "Party Lane", "party", "Celebrate anything",
              "Party supplies, gift wrap, sweets, flowers and candles.",
              ("party_supplies", "gift_wrapping", "gift_confectionery", "flowers", "candle_care"),
              _o(theme_color="#c026d3", urgency=True)),
    _Template("marketplace", "Bazaar Hub", "marketplace", "Millions of deals, one cart",
              "A general marketplace: electronics, fashion, home, toys, beauty, sports, kitchen and pets.",
              ("electronics", "apparel", "home_design", "toys_hobbies", "health_beauty", "sports", "kitchen_tools",
               "pet_care"),
              _o(theme_color="#f59e0b", sponsored_slots=2, social_proof=True, urgency=True, products_per_page=12,
                 recommendations="popular", payment_methods=["card", "paypal", "apple_pay", "bnpl", "bank_transfer"]),
              discount_share=0.35),
    _Template("flash_sale", "DealDrop", "flash_sale", "Today only. Gone at midnight.",
              "Daily deals with countdowns: accessories, kitchen, linen, shoes, plush and bath.",
              ("digital_accessories", "kitchen_tools", "home_linen", "footwear", "plush_toys", "bath_body"),
              _o(theme_color="#dc2626", urgency=True, social_proof=True, welcome_popup="coupon", coupon_code="DROP5",
                 coupon_percent=5, coupon_public=False, home_sections=["deals", "bestsellers"], service_fee=99),
              discount_share=0.75),
    _Template("senior_care", "Silver Care", "senior_care", "Comfort and care at home",
              "Home-care supplies, pharmacy care, wellness and first aid, in large print.",
              ("care_supplies", "pharmacy_care", "wellness", "first_aid_tools"),
              _o(theme_color="#0f766e", large_text=True, grid_columns=3, checkout_flow="one_page",
                 payment_methods=["card", "bank_transfer", "cash_on_delivery"], cookie_banner=False)),
)

_BY_ID = {t.id: t for t in TEMPLATES}
FROM_STORE_TEMPLATE = "from_store"

_GLYPHS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("drink", "water", "soda", "juice", "beer", "alcohol", "refresh", "coffee_station", "bubble_tea", "energy"), "bottle"),
    (("dairy",), "carton"),
    (("coffee", "tea"), "cup"),
    (("chips", "snack", "sweets", "confectionery", "checkout_impulse", "dessert"), "snack"),
    (("menu", "meal", "takeaway", "fresh_meals", "instant"), "bowl"),
    (("bakery", "baking", "breakfast"), "bread"),
    (("produce", "herbs", "plant_based", "seafood", "cheese", "pantry", "sauce", "spice", "frozen", "ice_cream"), "leaf"),
    (("pharmacy", "wellness", "nutrition", "first_aid", "care_supplies", "oral"), "cross"),
    (("skincare", "makeup", "beauty", "bath", "hair_care", "fragrance", "nail", "shaving"), "drop"),
    (("pet", "bird", "aquarium", "small_pet"), "paw"),
    (("baby",), "star"),
    (("toy", "plush", "puzzle", "games", "model", "miniature"), "block"),
    (("art", "craft", "stationery", "desk", "sewing", "leather", "wood", "ceramic", "books", "gift_wrapping"), "pencil"),
    (("electronics", "digital", "computer", "photography", "music"), "device"),
    (("kitchen", "dinnerware", "food_storage", "barista", "tea_brewing", "pantry_organization"), "pot"),
    (("home", "lighting", "linen", "candle", "bathroom", "storage", "laundry", "household", "cleaning", "refill"), "house"),
    (("garden", "indoor_plants", "seed", "propagation", "flowers"), "flower"),
    (("hair_accessories",), "gem"),
    (("apparel",), "shirt"),
    (("footwear", "shoe"), "shoe"),
    (("jewelry", "eyewear"), "gem"),
    (("sports", "yoga", "running", "swimming", "climbing", "bicycle", "cycling", "fishing"), "ball"),
    (("outdoor", "camp", "picnic", "travel", "souvenirs"), "tent"),
    (("hardware", "car_care"), "tool"),
    (("party",), "gift"),
)


def glyph_for(category_key: str) -> str:
    key = category_key.lower()
    return next((glyph for words, glyph in _GLYPHS if any(w in key for w in words)), "box")


def localized_amount(usd_cents: int, currency: str) -> int:
    """An amount set in US cents (a template's shipping fee), in `currency`'s minor unit, rounded as the catalog's
    prices are."""
    code = currency.upper()
    if usd_cents <= 0:
        return 0
    if code == "KRW":
        return max(100, round(usd_cents / 100 * _KRW_PER_USD / 100.0) * 100)
    if code == "JPY":
        return max(10, round(usd_cents * 1.5 / 10.0) * 10)
    return usd_cents


def _nice(amount: int, currency: str) -> int:
    """A believable price: KRW to 100 won, JPY to 10 yen, others ending in 9."""
    code = currency.upper()
    if code == "KRW":
        return max(100, round(amount / 100) * 100)
    if code == "JPY":
        return max(10, round(amount / 10) * 10)
    return max(9, round(amount / 10) * 10 - 1)


def highlights(options: SiteOptions) -> list[TemplateHighlight]:
    """What a template's options do differently from a plain shop, as codes the app names in its own language."""
    o = options
    found: list[tuple[bool, TemplateHighlight]] = [
        (o.device == "mobile", "mobile"), (o.quick_add, "quick_add"), (o.one_click_buy, "one_click"),
        (o.welcome_popup == "coupon", "coupon_popup"), (o.welcome_popup == "newsletter", "newsletter_popup"),
        (o.urgency, "urgency"), (o.social_proof, "social_proof"), (o.sponsored_slots > 0, "sponsored"),
        (o.preselected_addon_percent > 0, "addon"), (o.service_fee > 0, "service_fee"),
        (not o.guest_checkout, "account_required"), (o.checkout_flow == "one_page", "one_page_checkout"),
        ("bnpl" in o.payment_methods, "bnpl"), ("cash_on_delivery" in o.payment_methods, "cash_on_delivery"),
        (o.return_policy == "paid", "paid_returns"), (o.large_text, "large_text"),
        (o.shipping_fee == 0 or o.free_shipping_threshold == 0, "free_delivery"),
    ]
    return [code for on, code in found if on]


def template_summaries() -> list[OnlineTemplate]:
    out: list[OnlineTemplate] = []
    for t in TEMPLATES:
        items = [i for key in t.categories for i in CATALOG.get(key, [])[:_PRODUCTS_PER_CATEGORY]]
        out.append(OnlineTemplate(
            id=t.id, name=t.name, vertical=t.vertical, tagline=t.tagline, description=t.description,
            categories=len(t.categories), products=len(items), photos=sum(1 for i in items if i.en in PACKSHOT_URLS),
            theme_color=t.options.theme_color, highlights=highlights(t.options),
        ))
    return out


def template_ids() -> list[str]:
    return [t.id for t in TEMPLATES]


def _site_options(template: _Template, currency: str) -> SiteOptions:
    o = template.options
    return o.model_copy(update={
        "shipping_fee": localized_amount(o.shipping_fee, currency),
        "free_shipping_threshold": localized_amount(o.free_shipping_threshold, currency),
        "service_fee": localized_amount(o.service_fee, currency),
        "hero_text": o.hero_text or template.tagline,
    })


def _web_attributes(
    rng: random.Random, name: str, price: int, currency: str, discount_share: float,
) -> tuple[int, float, int, list[ProductBadge], int | None, int]:
    """(list price, rating, reviews, badges, stock, weekly sales) of one product."""
    list_price = 0
    if rng.random() < discount_share:
        list_price = _nice(round(price * (1 + rng.choice((0.1, 0.15, 0.2, 0.25, 0.3, 0.4)))), currency)
        if list_price <= price:
            list_price = 0
    rating = round(min(5.0, max(2.8, rng.gauss(4.3, 0.35))), 1)
    reviews = min(25_000, int(rng.lognormvariate(4.0, 1.2)))
    badges: list[ProductBadge] = []
    if any(w in name.lower() for w in _ECO_WORDS):
        badges.append("eco")
    if rng.random() < 0.12:
        badges.append("new")
    if rng.random() < 0.05:
        badges.append("limited")
    if rng.random() < 0.1:
        badges.append("sponsored")
    draw = rng.random()
    stock = 0 if draw < 0.05 else rng.randint(1, 5) if draw < 0.17 else None
    weekly = int(reviews * rng.uniform(0.02, 0.12)) + rng.randint(0, 20)
    return list_price, rating, reviews, badges, stock, weekly


def _mark_bestsellers(products: list[OnlineProduct]) -> None:
    """The two most-bought products of each category carry a best-seller badge."""
    by_category: dict[str, list[OnlineProduct]] = {}
    for p in products:
        by_category.setdefault(p.category_id, []).append(p)
    for group in by_category.values():
        for p in sorted(group, key=lambda p: (-p.weekly_sales, p.id))[:2]:
            if "bestseller" not in p.badges:
                p.badges.insert(0, "bestseller")


def _description(item: CatalogItem, label: str, rng: random.Random) -> str:
    phrases = ("Ready to ship today.", "A customer favourite.", "Great value for everyday use.",
               "Thoughtfully made and carefully packed.", "Easy to gift.", "Restocked every week.")
    return f"{item.en} from our {label.lower()} range. {rng.choice(phrases)}"


def build_site(
    template_id: str, *, site_id: str, currency: str = "USD", name: str = "", seed: int = 0, now: str = "",
) -> OnlineSite:
    template = _BY_ID.get(template_id)
    if template is None:
        raise ValueError(f"unknown online store template: {template_id}")
    categories: list[OnlineCategory] = []
    products: list[OnlineProduct] = []
    for key in template.categories:
        items = CATALOG.get(key, [])[:_PRODUCTS_PER_CATEGORY]
        if not items:
            continue
        en_label, ko_label = CATEGORY_LABELS.get(key, (key.replace("_", " ").title(),) * 2)
        label = ko_label if currency.upper() == "KRW" else en_label
        categories.append(OnlineCategory(id=key, name=label, glyph=glyph_for(key)))
        for item in items:
            product_name, price = localized(item, currency)
            rng = random.Random(stable_seed("online-product", template.id, key, item.en, seed))
            list_price, rating, reviews, badges, stock, weekly = _web_attributes(
                rng, item.en, price, currency, template.discount_share)
            tags = sorted({w for w in (*en_label.lower().split(), *item.en.lower().split()) if len(w) > 2} -
                          set(product_name.lower().split()))
            if product_name != item.en:
                tags.append(item.en)
            products.append(OnlineProduct(
                id=f"p{len(products) + 1:03d}", name=product_name, category_id=key, price=price, list_price=list_price,
                rating=rating, reviews=reviews, badges=badges, stock=stock, description=_description(item, en_label, rng),
                tags=tags, image_url=PACKSHOT_URLS.get(item.en, ""), weekly_sales=weekly,
            ))
    _mark_bestsellers(products)
    return OnlineSite(
        id=site_id, name=(name or template.name)[:60], template_id=template.id, currency=currency.upper(),
        tagline=template.tagline, categories=categories, products=products,
        options=_site_options(template, currency), created_at=now, updated_at=now,
    )


def site_from_store(store: Store, *, site_id: str, name: str, currency: str, seed: int = 0, now: str = "") -> OnlineSite:
    """The physical store's assortment as a web shop: one category per shelf sign, each product once (its first
    placement), shelf promotions as sale prices."""
    categories: list[OnlineCategory] = []
    products: list[OnlineProduct] = []
    seen: set[str] = set()
    category_ids: dict[str, str] = {}
    for rack in store.racks:
        items = [item for slot in rack.slots for item in slot.items if item.sku not in seen]
        if not items:
            continue
        label = category_label(rack)
        key = category_ids.get(label.lower())
        if key is None:
            key = f"c{len(categories) + 1:03d}"
            category_ids[label.lower()] = key
            categories.append(OnlineCategory(id=key, name=label[:80], glyph=glyph_for(label)))
        for item in items:
            if item.sku in seen:
                continue
            seen.add(item.sku)
            rng = random.Random(stable_seed("online-store-product", item.sku, seed))
            _, rating, reviews, badges, stock, weekly = _web_attributes(rng, item.name, item.price, currency, 0.0)
            products.append(OnlineProduct(
                id=f"p{len(products) + 1:03d}", name=item.name[:120], category_id=key, price=item.price,
                list_price=item.regular_price if item.regular_price > item.price else 0, rating=rating, reviews=reviews,
                badges=badges, stock=stock, description=f"{item.name} from the {label} shelf."[:400],
                tags=[w for w in label.lower().split() if len(w) > 2], image_url=item.image_url or "",
                weekly_sales=weekly, sku=item.sku,
            ))
    if not products:
        raise ValueError("this layout has no products on its shelves yet")
    _mark_bestsellers(products)
    return OnlineSite(
        id=site_id, name=name[:60] or "Online store", template_id=FROM_STORE_TEMPLATE, currency=currency.upper(),
        tagline="The same shelves, online", categories=categories, products=products,
        options=SiteOptions(shipping_fee=localized_amount(499, currency),
                            free_shipping_threshold=localized_amount(3500, currency), hero_text="Shop our store online"),
        created_at=now, updated_at=now,
    )
