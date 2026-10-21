"""Generic product catalog for generated stores (no brand names), in English and Korean.

Prices are USD cents; Korean stores convert at ~1,350 KRW/USD and round to 100 won, which
lands on typical Korean convenience-store price points.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogItem:
    en: str
    ko: str
    usd_cents: int


def _items(rows: list[tuple[str, str, int]]) -> list[CatalogItem]:
    return [CatalogItem(en, ko, cents) for en, ko, cents in rows]


CATALOG: dict[str, list[CatalogItem]] = {
    "soft_drinks": _items([
        ("Cola 500ml", "콜라 500ml", 229), ("Zero Cola 500ml", "제로콜라 500ml", 229), ("Lemon-Lime Soda 500ml", "사이다 500ml", 219),
        ("Orange Soda 355ml", "오렌지 탄산 355ml", 179), ("Ginger Ale 355ml", "진저에일 355ml", 189), ("Grape Soda 355ml", "포도 탄산 355ml", 179),
        ("Sparkling Water Lemon 500ml", "레몬 탄산수 500ml", 179), ("Sparkling Water Plain 500ml", "탄산수 500ml", 169),
        ("Cola 1.5L", "콜라 1.5L", 349), ("Lemon-Lime Soda 1.5L", "사이다 1.5L", 339), ("Root Beer 355ml", "루트비어 355ml", 189),
        ("Peach Iced Tea 500ml", "복숭아 아이스티 500ml", 199), ("Lemon Iced Tea 500ml", "레몬 아이스티 500ml", 199),
        ("Green Tea 500ml", "녹차 500ml", 189), ("Barley Tea 500ml", "보리차 500ml", 169), ("Corn Silk Tea 500ml", "옥수수수염차 500ml", 179),
    ]),
    "water_sports": _items([
        ("Mineral Water 500ml", "생수 500ml", 99), ("Mineral Water 2L", "생수 2L", 179), ("Sports Drink 600ml", "이온음료 600ml", 219),
        ("Sports Drink Lemon 600ml", "이온음료 레몬 600ml", 219), ("Vitamin Water 500ml", "비타민워터 500ml", 239),
        ("Coconut Water 330ml", "코코넛워터 330ml", 279), ("Electrolyte Drink 500ml", "전해질음료 500ml", 249), ("Alkaline Water 1L", "알칼리수 1L", 229),
    ]),
    "energy_coffee": _items([
        ("Energy Drink 250ml", "에너지드링크 250ml", 249), ("Energy Drink Zero 355ml", "에너지드링크 제로 355ml", 299),
        ("Cold Brew Coffee 300ml", "콜드브루 커피 300ml", 299), ("Cafe Latte Bottle 300ml", "카페라떼 300ml", 279),
        ("Canned Coffee 175ml", "캔커피 175ml", 149), ("Vanilla Latte 300ml", "바닐라라떼 300ml", 299), ("Caramel Macchiato 300ml", "카라멜마끼아또 300ml", 299),
        ("Americano Bottle 400ml", "아메리카노 400ml", 249), ("Protein Shake 330ml", "프로틴 쉐이크 330ml", 349), ("Vitamin Shot 100ml", "비타민 음료 100ml", 129),
    ]),
    "dairy": _items([
        ("Milk 1L", "우유 1L", 299), ("Milk 200ml", "우유 200ml", 99), ("Banana Milk 240ml", "바나나우유 240ml", 159),
        ("Strawberry Milk 240ml", "딸기우유 240ml", 159), ("Chocolate Milk 240ml", "초코우유 240ml", 159), ("Drinking Yogurt 150ml", "마시는 요구르트 150ml", 149),
        ("Greek Yogurt Cup", "그릭요거트", 199), ("Soy Milk 190ml", "두유 190ml", 109), ("String Cheese 2pk", "스트링치즈 2입", 249), ("Probiotic Drink 5pk", "유산균 음료 5입", 299),
    ]),
    "beer_alcohol": _items([
        ("Lager Beer 500ml", "라거 맥주 500ml", 299), ("Lager Beer 355ml 4pk", "라거 맥주 355ml 4캔", 999), ("Craft IPA 500ml", "수제 IPA 500ml", 449),
        ("Wheat Beer 500ml", "밀맥주 500ml", 349), ("Soju 360ml", "소주 360ml", 179), ("Fruit Soju 360ml", "과일소주 360ml", 199),
        ("Makgeolli 750ml", "막걸리 750ml", 199), ("Highball Lemon 500ml", "레몬 하이볼 500ml", 349), ("House Red Wine 750ml", "레드와인 750ml", 999),
        ("Non-alcoholic Beer 355ml", "무알콜 맥주 355ml", 229),
    ]),
    "chips": _items([
        ("Potato Chips Original", "감자칩 오리지널", 199), ("Potato Chips Sour Cream", "감자칩 사워크림", 199), ("Tortilla Chips Nacho", "나쵸칩", 219),
        ("Shrimp Crackers", "새우스낵", 159), ("Corn Puffs", "콘스낵", 159), ("Honey Butter Chips", "허니버터칩", 219), ("Onion Rings Snack", "양파링 스낵", 169),
        ("Popcorn Butter", "버터 팝콘", 199), ("Pretzels", "프레첼", 189), ("Seaweed Snack", "김스낵", 149), ("Rice Crackers", "쌀과자", 169), ("Cheese Balls", "치즈볼", 199),
    ]),
    "sweets": _items([
        ("Milk Chocolate Bar", "밀크초콜릿", 149), ("Peanut Chocolate Bar", "땅콩 초코바", 159), ("Gummy Bears", "젤리 곰", 179),
        ("Sour Gummies", "새콤 젤리", 179), ("Mint Gum", "민트껌", 99), ("Hard Candy", "사탕", 129), ("Chocolate Cookies", "초코칩쿠키", 229),
        ("Choco Pie 6pk", "초코파이 6입", 349), ("Wafer Bar", "웨하스", 129), ("Caramel Popcorn", "캬라멜팝콘", 199), ("Marshmallows", "마시멜로", 169), ("Chocolate Biscuit Sticks", "초코 막대과자", 159),
    ]),
    "instant_food": _items([
        ("Spicy Cup Ramen", "매운 컵라면", 149), ("Mild Cup Ramen", "순한 컵라면", 149), ("Big Bowl Noodles", "큰사발 라면", 189),
        ("Black Bean Noodles Cup", "짜장 컵라면", 169), ("Udon Bowl", "우동 컵", 199), ("Instant Rice", "즉석밥", 149), ("Instant Rice 3pk", "즉석밥 3입", 399),
        ("Curry Pouch", "레토르트 카레", 229), ("Instant Soup", "즉석 수프", 179), ("Tuna Can", "참치캔", 249), ("Spam Can", "햄 통조림", 449), ("Ramen 5pk", "라면 5입", 499),
    ]),
    "fresh_meals": _items([
        ("Tuna Mayo Rice Ball", "참치마요 삼각김밥", 129), ("Bulgogi Rice Ball", "불고기 삼각김밥", 139), ("Kimbap Roll", "김밥", 299),
        ("Ham & Cheese Sandwich", "햄치즈 샌드위치", 329), ("Egg Salad Sandwich", "에그 샌드위치", 299), ("Chicken Wrap", "치킨 랩", 379),
        ("Lunch Box Pork Cutlet", "돈까스 도시락", 549), ("Lunch Box Bulgogi", "불고기 도시락", 549), ("Garden Salad", "샐러드", 449),
        ("Chicken Breast Salad", "닭가슴살 샐러드", 499), ("Hamburger", "햄버거", 299), ("Spicy Rice Cakes Cup", "떡볶이 컵", 299),
    ]),
    "bakery": _items([
        ("Croissant", "크루아상", 249), ("Cream Bun", "크림빵", 179), ("Red Bean Bun", "단팥빵", 179), ("Cheese Bagel", "치즈 베이글", 249),
        ("Blueberry Muffin", "블루베리 머핀", 279), ("Chocolate Donut", "초코 도넛", 199), ("Castella Cake", "카스테라", 229), ("Sliced Bread", "식빵", 299),
        ("Garlic Bread", "마늘빵", 219), ("Cinnamon Roll", "시나몬롤", 279), ("Cheesecake Slice", "치즈케이크", 399), ("Egg Tart", "에그타르트", 229),
    ]),
    "ice_cream": _items([
        ("Vanilla Cone", "바닐라 콘", 179), ("Chocolate Cone", "초코 콘", 179), ("Melon Bar", "메론바", 129), ("Fish-shaped Ice Cream", "붕어 아이스크림", 199),
        ("Strawberry Ice Bar", "딸기 아이스바", 129), ("Mochi Ice Cream", "찹쌀떡 아이스", 199), ("Ice Cream Pint Cookies", "쿠키 아이스크림 파인트", 699),
        ("Ice Cream Sandwich", "아이스 샌드", 179), ("Shaved Ice Cup", "빙수 컵", 299), ("Lemon Sorbet Cup", "레몬 샤베트", 199),
        ("Frozen Dumplings", "냉동만두", 599), ("Frozen Pizza Slice", "냉동 피자", 399),
    ]),
    "household": _items([
        ("Tissues", "휴지", 199), ("Wet Wipes", "물티슈", 249), ("Paper Towels", "키친타월", 349), ("Dish Soap", "주방세제", 399),
        ("Laundry Detergent Small", "세탁세제 소용량", 599), ("Trash Bags 20pk", "종량제봉투 20매", 499), ("AA Batteries 4pk", "건전지 AA 4입", 599),
        ("Phone Charging Cable", "충전 케이블", 999), ("Umbrella", "우산", 799), ("Disposable Raincoat", "일회용 우비", 299), ("Lighter", "라이터", 99), ("Light Bulb", "전구", 449),
    ]),
    "health_beauty": _items([
        ("Face Masks 5pk", "마스크 5매", 399), ("Hand Sanitizer", "손소독제", 299), ("Adhesive Bandages", "밴드", 249), ("Lip Balm", "립밤", 299),
        ("Sunscreen SPF50", "선크림 SPF50", 1299), ("Toothbrush", "칫솔", 249), ("Toothpaste Travel", "치약 휴대용", 199), ("Shampoo Travel", "샴푸 소용량", 299),
        ("Facial Cleanser", "폼클렌저", 699), ("Sheet Face Mask", "마스크팩", 199), ("Hand Cream", "핸드크림", 499), ("Cotton Pads", "화장솜", 249),
        ("Vitamin C Tablets", "비타민C 정", 899), ("Eye Drops (artificial tears)", "인공눈물", 599), ("Hangover Drink", "숙취해소 음료", 399), ("Heat Packs", "핫팩", 129),
    ]),
    "stationery": _items([
        ("Ballpoint Pens 3pk", "볼펜 3입", 249), ("Notebook A5", "노트 A5", 199), ("Highlighters", "형광펜", 299), ("Sticky Notes", "포스트잇", 249),
        ("Correction Tape", "수정테이프", 249), ("Glue Stick", "딱풀", 149), ("Scissors", "가위", 299), ("Envelope 5pk", "봉투 5매", 149),
    ]),
    "car_care": _items([
        ("Windshield Washer Fluid", "워셔액", 499), ("Car Air Freshener", "차량용 방향제", 399), ("Microfiber Cloth", "극세사 타월", 299),
        ("Engine Oil 1L", "엔진오일 1L", 1199), ("Phone Car Mount", "차량용 거치대", 999), ("Ice Scraper", "성에제거기", 399),
    ]),
    "fresh_produce": _items([
        ("Bananas", "바나나", 249), ("Apples 2pk", "사과 2입", 399), ("Cherry Tomatoes", "방울토마토", 449), ("Cucumber", "오이", 99),
        ("Lettuce", "상추", 249), ("Eggs 10pk", "계란 10구", 399), ("Tofu", "두부", 199), ("Green Onion", "대파", 199),
        ("Onions 3pk", "양파 3입", 249), ("Potatoes", "감자", 299), ("Kimchi 500g", "김치 500g", 599), ("Mandarins", "귤", 399),
    ]),
    "souvenirs": _items([
        ("Postcard Set", "엽서 세트", 499), ("Keychain", "키링", 599), ("Local Snack Gift Box", "지역 특산 과자세트", 1499), ("Fridge Magnet", "냉장고 자석", 399),
        ("Travel Adapter", "여행용 어댑터", 1299), ("Transit Card", "교통카드", 499), ("Ginseng Candy", "홍삼 캔디", 699), ("Honey Citron Tea", "유자차", 899),
    ]),
    "checkout_impulse": _items([
        ("Mint Gum", "민트껌", 99), ("Breath Mints", "구강 캔디", 149), ("Chocolate Bar Mini", "미니 초콜릿", 79), ("Lollipop", "막대사탕", 49),
        ("Jelly Pouch", "젤리 파우치", 129), ("Lighter", "라이터", 99), ("Hot Pack Mini", "미니 핫팩", 99), ("Energy Shot 60ml", "에너지샷 60ml", 199),
    ]),
    "coffee_station": _items([
        ("Hot Americano", "아메리카노 (즉석)", 120), ("Hot Cafe Latte", "카페라떼 (즉석)", 190), ("Iced Americano", "아이스 아메리카노", 150),
        ("Iced Latte", "아이스 라떼", 220), ("Hot Chocolate", "핫초코", 200), ("Iced Cup", "얼음컵", 69), ("Hot Barley Tea", "따뜻한 보리차", 120), ("Steamed Bun", "호빵", 149),
    ]),
}

# Rack label shown in the store (and read by rule-based shoppers / scenario category matching).
CATEGORY_LABELS: dict[str, tuple[str, str]] = {
    "soft_drinks": ("Drinks", "음료"), "water_sports": ("Water & Sports Drinks", "생수·이온음료"),
    "energy_coffee": ("Energy & Coffee Drinks", "에너지·커피음료"), "dairy": ("Dairy Drinks", "유제품·우유"),
    "beer_alcohol": ("Beer & Alcohol", "주류·맥주"), "chips": ("Snacks", "과자·스낵"), "sweets": ("Candy & Cookies", "초콜릿·사탕"),
    "instant_food": ("Instant Noodles & Food", "라면·간편식"), "fresh_meals": ("Fresh Meals & Lunch", "도시락·삼각김밥"),
    "bakery": ("Bakery & Bread", "빵·베이커리"), "ice_cream": ("Ice Cream & Frozen", "아이스크림·냉동"),
    "household": ("Household & Daily", "생활용품"), "health_beauty": ("Health & Beauty", "건강·뷰티"),
    "stationery": ("Stationery", "문구"), "car_care": ("Car Care", "차량용품"), "fresh_produce": ("Fresh Produce", "신선식품·채소"),
    "souvenirs": ("Gifts & Travel", "기념품·여행용품"), "checkout_impulse": ("Checkout Treats", "계산대 간식"),
    "coffee_station": ("Coffee Station (hot coffee)", "즉석 커피"),
}

# Specialty assortments use generic English labels in both price modes.
# Pharmacy entries are OTC retail goods; no prescription or dispensing simulation.
_SPECIALTY: dict[str, list[tuple[str, int]]] = {
    "pharmacy_care": [("Adhesive Bandages 30pk", 399), ("Sterile Gauze Pads", 549), ("Digital Thermometer", 1299), ("Saline Nasal Spray", 699), ("Antiseptic Wipes 20pk", 449), ("First Aid Kit", 1899), ("Elastic Support Bandage", 799), ("Reusable Cold Pack", 649)],
    "wellness": [("Vitamin C Tablets 60pk", 999), ("Multivitamin Tablets 30pk", 1299), ("Electrolyte Sachets 6pk", 749), ("Hand Sanitizer 100ml", 299), ("Face Masks 10pk", 499), ("Lip Balm", 349), ("Sensitive Toothpaste", 599), ("Sunscreen SPF50", 1499)],
    "pantry": [("Long Grain Rice 2kg", 599), ("Rolled Oats 1kg", 449), ("Pasta 500g", 229), ("Tomato Sauce 400g", 299), ("Olive Oil 500ml", 899), ("Canned Chickpeas 400g", 179), ("All Purpose Flour 1kg", 249), ("Ground Coffee 250g", 799)],
    "restaurant_menu": [("Grilled Chicken Rice Bowl", 1199), ("Vegetable Rice Bowl", 999), ("Tomato Pasta", 1299), ("Mushroom Soup", 699), ("Garden Salad", 899), ("Cheese Toastie", 749), ("Roasted Vegetable Wrap", 849), ("Seasonal Lunch Set", 1499)],
    "cafe_menu": [("Espresso", 250), ("Flat White", 425), ("Oat Milk Latte", 495), ("Filter Coffee", 350), ("Matcha Latte", 525), ("Earl Grey Tea", 375), ("Decaf Cappuccino", 450), ("Iced Mocha", 525)],
    "desserts": [("Chocolate Brownie", 399), ("Lemon Tart", 499), ("Vanilla Cheesecake Slice", 599), ("Fruit Yogurt Parfait", 449), ("Chocolate Chip Muffin", 349), ("Strawberry Shortcake", 649), ("Almond Cookie", 249), ("Cinnamon Roll", 399)],
    "apparel": [("Cotton T-Shirt", 1999), ("Linen Shirt", 3999), ("Denim Jeans", 5999), ("Knit Cardigan", 4999), ("Canvas Tote Bag", 1499), ("Cotton Socks 3pk", 999), ("Baseball Cap", 1799), ("Lightweight Scarf", 2499)],
    "books": [("Contemporary Fiction Paperback", 1499), ("Travel Guide", 1999), ("Everyday Cooking Book", 2499), ("Children's Picture Book", 1299), ("Design & Architecture Book", 3499), ("Pocket Poetry Collection", 999), ("Nature Field Guide", 1899), ("Weekly Planner", 1199)],
    "electronics": [("USB-C Cable 1m", 1299), ("Wireless Earbuds", 4999), ("Portable Power Bank", 2999), ("Phone Stand", 1499), ("Wireless Mouse", 2499), ("Bluetooth Speaker", 3999), ("USB Wall Charger", 1999), ("Screen Cleaning Kit", 899)],
    "home_design": [("Ceramic Vase", 2499), ("Linen Cushion Cover", 1999), ("Scented Candle", 1499), ("Stoneware Mug", 1299), ("Cotton Throw Blanket", 3999), ("Desk Lamp", 4999), ("Wooden Serving Tray", 2999), ("Small Indoor Planter", 1799)],
    "pet_care": [("Dry Cat Food 1kg", 1299), ("Dry Dog Food 2kg", 1999), ("Cat Treats 60g", 399), ("Dog Treats 100g", 499), ("Pet Shampoo", 899), ("Cat Litter 5L", 999), ("Rope Chew Toy", 699), ("Pet Feeding Bowl", 799)],
    "sports": [("Yoga Mat", 2499), ("Resistance Band Set", 1999), ("Reusable Sports Bottle", 1499), ("Running Socks", 999), ("Tennis Balls 3pk", 799), ("Swimming Goggles", 1799), ("Fitness Towel", 1299), ("Foam Roller", 2999)],
    "flowers": [("Seasonal Flower Bouquet", 2499), ("Mini Succulent", 799), ("Potted Herb", 599), ("Orchid Plant", 2999), ("Flower Food Sachets", 299), ("Greeting Card", 399), ("Gift Wrap", 249), ("Dried Flower Bundle", 1499)],
}
for _category, _products in _SPECIALTY.items():
    CATALOG[_category] = [CatalogItem(name, name, price) for name, price in _products]
    _label = _category.replace("_", " ").title()
    CATEGORY_LABELS[_category] = (_label, _label)

ZERO_DECIMAL = {"KRW", "JPY"}
_KRW_PER_USD = 1350


def localized(item: CatalogItem, currency: str) -> tuple[str, int]:
    """(name, price in the currency's minor unit)."""
    code = currency.upper()
    if code == "KRW":
        return item.ko, max(100, round(item.usd_cents / 100 * _KRW_PER_USD / 100.0) * 100)
    if code == "JPY":
        return item.en, max(10, round(item.usd_cents * 1.5 / 10.0) * 10)
    return item.en, item.usd_cents


def category_label(category: str, currency: str) -> str:
    en, ko = CATEGORY_LABELS.get(category, (category, category))
    return ko if currency.upper() == "KRW" else en
