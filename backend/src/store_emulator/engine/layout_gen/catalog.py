"""Generic product catalog for generated stores (no brand names), in English and Korean.

Prices are USD cents; Korean stores convert at ~1,350 KRW/USD and round to 100 won, which
lands on typical Korean convenience-store price points.
"""

import hashlib
import json
from dataclasses import dataclass
from .catalog_expansion import PACKSHOT_URLS, PRODUCTS
from store_emulator.domain.rack import SlotItem


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
    "refill_goods": [
        ("Rolled Oats Refill 1kg", 499), ("Brown Rice Refill 1kg", 449), ("Red Lentils Refill 1kg", 599),
        ("Chickpeas Refill 1kg", 549), ("Wholegrain Pasta Refill 500g", 349), ("Mixed Nuts Refill 500g", 999),
        ("Pumpkin Seeds Refill 250g", 599), ("Ground Coffee Refill 250g", 899), ("Loose Black Tea Refill 100g", 699),
        ("Dish Soap Refill 500ml", 499), ("Laundry Liquid Refill 1L", 899), ("Reusable Produce Bags 3pk", 799),
    ],
    "care_supplies": [
        ("Adjustable Walking Cane", 2499), ("Folding Walking Frame", 7999), ("Shower Stool", 4999),
        ("Long-Handled Reaching Aid", 1999), ("Weekly Pill Organizer", 899), ("Digital Thermometer", 1299),
        ("Reusable Cold Pack", 999), ("Soft Knee Support", 1599), ("Large-Grip Cutlery Set", 2499),
        ("Non-Slip Bath Mat", 1999), ("Bedside Storage Caddy", 1799), ("Large-Print Medication Log", 699),
    ],
    "fragrances": [
        ("Citrus Eau de Toilette 50ml", 4999), ("Rose Eau de Parfum 50ml", 6999), ("Cedar Eau de Parfum 50ml", 7499),
        ("Green Tea Body Mist 100ml", 1999), ("Vanilla Perfume Oil 10ml", 2499), ("Amber Travel Spray 10ml", 2199),
        ("Fragrance Discovery Set 6pc", 2999), ("Lavender Room Spray 100ml", 1799), ("Fig Reed Diffuser 100ml", 2499),
        ("Sandalwood Candle 180g", 2299), ("Refillable Perfume Atomizer", 1299), ("Fragrance Gift Pouch", 499),
    ],
    "bubble_tea_menu": [
        ("Classic Pearl Milk Tea", 549), ("Brown Sugar Pearl Milk", 649), ("Taro Milk Tea", 599),
        ("Matcha Pearl Latte", 649), ("Thai Milk Tea", 599), ("Jasmine Milk Tea", 549),
        ("Mango Fruit Tea", 599), ("Passion Fruit Green Tea", 579), ("Peach Oolong Tea", 579),
        ("Lychee Coconut Jelly Tea", 629), ("Oat Milk Pearl Tea", 649), ("Mini Milk Tea Tasting Set", 899),
    ],
    "korean_menu": [
        ("Vegetable Bibimbap", 1099), ("Beef Bulgogi Rice Bowl", 1499), ("Spicy Pork Rice Bowl", 1299),
        ("Kimchi Fried Rice", 1049), ("Tofu Kimchi Stew", 1199), ("Soybean Paste Stew", 1099),
        ("Cold Buckwheat Noodles", 1249), ("Vegetable Gimbap", 849), ("Spicy Rice Cakes", 799),
        ("Kimchi Pancake", 949), ("Steamed Mandu 6pc", 699), ("Seasonal Banchan Set", 499),
    ],
    "burger_menu": [
        ("Classic Beef Burger", 899), ("Cheddar Cheeseburger", 999), ("Double Beef Burger", 1299),
        ("Grilled Chicken Burger", 1049), ("Spicy Chicken Burger", 999), ("Plant-Based Burger", 1099),
        ("Mushroom Swiss Burger", 1149), ("Mini Burger", 649), ("Skin-On Fries", 349),
        ("Sweet Potato Fries", 449), ("Crispy Onion Rings", 499), ("Burger Fries & Drink Meal", 1499),
    ],
    "salad_menu": [
        ("Grilled Chicken Caesar Salad", 1199), ("Roasted Vegetable Grain Bowl", 1099), ("Chickpea Quinoa Salad", 1049),
        ("Salmon Avocado Grain Bowl", 1499), ("Tofu Sesame Grain Bowl", 1149), ("Mediterranean Lentil Bowl", 1099),
        ("Beet & Feta Salad", 1049), ("Crunchy Cabbage Slaw", 449), ("Tomato Lentil Soup", 649),
        ("Roasted Sweet Potato Side", 499), ("Whole Grain Bread Roll", 249), ("Salad & Soup Lunch Set", 1449),
    ],
    "scoop_menu": [
        ("Vanilla Ice Cream Cone", 349), ("Chocolate Ice Cream Cone", 349), ("Strawberry Ice Cream Cup", 399),
        ("Matcha Gelato Cup", 449), ("Pistachio Gelato Cup", 499), ("Mango Sorbet Cup", 449),
        ("Lemon Sorbet Cup", 399), ("Chocolate Brownie Sundae", 749), ("Banana Split", 899),
        ("Vanilla Milkshake", 599), ("Chocolate Milkshake", 649), ("Mini Scoop Tasting Flight", 799),
    ],
    "pizza_menu": [
        ("Margherita Pizza", 1299), ("Pepperoni Pizza", 1499), ("Roasted Vegetable Pizza", 1399),
        ("Four Cheese Pizza", 1599), ("Mushroom Pizza", 1399), ("Chicken Pesto Pizza", 1699),
        ("Margherita Slice", 399), ("Pepperoni Slice", 449), ("Garlic Bread", 499),
        ("Mixed Leaf Side Salad", 599), ("Tomato Mozzarella Salad", 799), ("Pizza & Drink Lunch Set", 1199),
    ],
    "sushi_menu": [
        ("Salmon Nigiri 2pc", 599), ("Tuna Nigiri 2pc", 699), ("Avocado Maki 6pc", 649),
        ("Cucumber Maki 6pc", 549), ("California Roll 8pc", 1099), ("Spicy Tuna Roll 8pc", 1199),
        ("Vegetable Sushi Set", 1399), ("Mixed Nigiri Set", 1899), ("Salmon Rice Bowl", 1599),
        ("Miso Soup Cup", 349), ("Edamame Cup", 449), ("Seaweed Side Salad", 499),
    ],
    "noodle_menu": [
        ("Shoyu Ramen", 1299), ("Miso Ramen", 1399), ("Vegetable Ramen", 1199),
        ("Spicy Sesame Noodles", 1299), ("Chicken Udon", 1399), ("Mushroom Udon", 1299),
        ("Chilled Soba", 1199), ("Vegetable Stir-Fried Noodles", 1299), ("Beef Noodle Soup", 1499),
        ("Vegetable Dumplings 5pc", 599), ("Steamed Rice Side", 299), ("Noodle & Dumpling Set", 1699),
    ],
    "juice_menu": [
        ("Orange Juice 350ml", 549), ("Apple Juice 350ml", 499), ("Carrot Ginger Juice 350ml", 599),
        ("Green Vegetable Juice 350ml", 649), ("Pineapple Mint Juice 350ml", 599), ("Watermelon Juice 350ml", 549),
        ("Berry Banana Smoothie", 699), ("Mango Yogurt Smoothie", 749), ("Oat Banana Smoothie", 649),
        ("Strawberry Yogurt Smoothie", 699), ("Tropical Fruit Cup", 499), ("Berry Granola Bowl", 899),
    ],
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
    "tea_menu": [("Loose Leaf Green Tea 50g", 899), ("Jasmine Tea Pot", 595), ("Roasted Oolong Tea Pot", 695), ("Chamomile Tea", 425), ("Peppermint Infusion", 425), ("Chai Latte", 525), ("Iced Peach Tea", 495), ("Matcha Cookie", 325), ("Tea Sampler Gift Box", 1899), ("Ceramic Tea Cup", 1299), ("Honey Lemon Tea", 495), ("Decaf Rooibos Tea", 450)],
    "hardware": [("Claw Hammer", 1499), ("Screwdriver Set", 1999), ("Measuring Tape 5m", 999), ("Adjustable Wrench", 1799), ("Wall Plugs & Screws", 699), ("Painter's Tape", 499), ("Safety Glasses", 899), ("LED Work Light", 2499), ("Sanding Sheets 10pk", 799), ("Work Gloves", 1199), ("Spirit Level", 1599), ("Wood Glue", 649)],
    "toys_hobbies": [("Wooden Building Blocks", 2499), ("Jigsaw Puzzle 500pc", 1499), ("Family Board Game", 2999), ("Model Car", 1299), ("Sketching Kit", 1999), ("Soft Plush Bear", 1799), ("Card Game", 999), ("Modeling Clay Set", 1199), ("Science Activity Kit", 2499), ("Origami Paper Set", 699), ("Train Starter Set", 3999), ("Craft Bead Kit", 1599)],
    "footwear": [
        ("Everyday Canvas Sneakers", 3999), ("Mesh Running Shoes", 6999), ("Leather Loafers", 8999),
        ("Trail Walking Shoes", 7999), ("Comfort Sandals", 4499), ("Ankle Boots", 9999),
        ("Kids' Velcro Sneakers", 3499), ("Indoor Slippers", 1999), ("Performance Socks 3pk", 1299),
        ("Cushioned Insoles", 1499), ("Shoe Care Brush", 899), ("Replacement Shoelaces", 499),
    ],
    "baby_supplies": [
        ("Newborn Diapers 40pk", 1499), ("Toddler Diapers 36pk", 1599), ("Baby Wet Wipes 80pk", 349),
        ("Cotton Baby Bibs 3pk", 1299), ("Muslin Swaddle Blanket", 1999), ("Baby Feeding Bottle", 999),
        ("Silicone Feeding Bowl", 1299), ("Training Cup", 899), ("Cotton Baby Bodysuit", 1499),
        ("Soft Baby Washcloths 6pk", 999), ("Baby Bath Towel", 1799), ("Diaper Changing Mat", 2499),
    ],
    "travel_gear": [
        ("Cabin Travel Backpack", 5999), ("Packing Cubes 3pc", 2499), ("Travel Neck Pillow", 1999),
        ("Luggage Tag Set", 799), ("Passport Wallet", 1799), ("Travel Adapter", 1999),
        ("Luggage Strap", 999), ("Refillable Travel Bottles 4pk", 1299), ("Compact Travel Umbrella", 1699),
        ("Travel Eye Mask", 899), ("Foldable Day Bag", 1999), ("Compact Toiletry Pouch", 1499),
    ],
    "eyewear": [
        ("Classic Round Frame", 7999), ("Rectangular Frame", 8999), ("Lightweight Frame", 9999),
        ("Polarized Sunglasses", 6999), ("Clip-On Sunglasses", 2499), ("Sports Eyewear", 5999),
        ("Hard Glasses Case", 1299), ("Eyeglass Cord", 799), ("Lens Cleaning Spray 60ml", 599),
        ("Microfiber Cloth Set", 499), ("Lens Cleaning Wipes 30pk", 699), ("Eyewear Travel Pouch", 999),
    ],
    "jewelry": [
        ("Sterling Silver Ring", 4999), ("Gold-Plated Stud Earrings", 3999), ("Beaded Bracelet", 1999),
        ("Pendant Necklace", 5999), ("Chain Necklace", 4499), ("Pearl-Style Earrings", 2999),
        ("Jewelry Travel Case", 2499), ("Watch Strap", 1999), ("Minimalist Watch", 8999),
        ("Floral Brooch", 2499), ("Jewelry Cleaning Cloth", 599), ("Gift Presentation Box", 799),
    ],
    "music_gear": [
        ("Acoustic Guitar", 19999), ("Soprano Ukulele", 5999), ("Portable Keyboard", 14999),
        ("Practice Drum Pad", 2999), ("Guitar Strings Set", 999), ("Instrument Cable 3m", 1499),
        ("Clip-On Tuner", 1999), ("Guitar Picks 12pk", 599), ("Folding Music Stand", 2499),
        ("Guitar Strap", 1999), ("Keyboard Sustain Pedal", 2499), ("Instrument Cleaning Kit", 1299),
    ],
    "garden_supplies": [
        ("Potting Mix 10L", 899), ("Vegetable Seed Pack", 299), ("Wildflower Seed Pack", 349),
        ("Seedling Tray", 599), ("Terracotta Pot 20cm", 1299), ("Watering Can 5L", 1999),
        ("Garden Hand Trowel", 999), ("Pruning Shears", 1799), ("Gardening Gloves", 899),
        ("Plant Support Stakes 6pk", 749), ("Plant Labels 20pk", 449), ("Garden Hose Nozzle", 1499),
    ],
    "art_craft": [
        ("Watercolor Paint Set", 1999), ("Acrylic Paint Set", 2499), ("Paint Brush Set", 1499),
        ("Sketch Pad A4", 899), ("Drawing Pencils 12pk", 1299), ("Canvas Panel 30cm", 999),
        ("Air-Dry Clay 1kg", 1199), ("Embroidery Starter Kit", 1799), ("Cotton Yarn Ball", 599),
        ("Craft Cutting Mat", 1999), ("Paper Craft Pack", 799), ("Washable Craft Glue", 499),
    ],
    "mediterranean_menu": [
        ("Falafel Pita Wrap", 1099), ("Grilled Chicken Pita", 1299), ("Roasted Vegetable Pita", 1099),
        ("Hummus & Pita Plate", 899), ("Baba Ganoush & Pita Plate", 949), ("Greek Salad Bowl", 1199),
        ("Tabbouleh Salad Bowl", 1099), ("Lentil & Herb Bowl", 1199), ("Chicken Rice Plate", 1499),
        ("Stuffed Vine Leaves 6pc", 799), ("Olive & Feta Side", 599), ("Baklava 2pc", 549),
    ],
    "mexican_menu": [
        ("Chicken Burrito", 1199), ("Bean & Rice Burrito", 999), ("Beef Burrito Bowl", 1399),
        ("Grilled Vegetable Bowl", 1099), ("Chicken Tacos 3pc", 1199), ("Mushroom Tacos 3pc", 1099),
        ("Cheese Quesadilla", 899), ("Chicken Quesadilla", 1199), ("Loaded Nachos", 1099),
        ("Guacamole & Tortilla Chips", 749), ("Corn & Lime Side", 499), ("Cinnamon Churros 3pc", 549),
    ],
    "indian_menu": [
        ("Butter Chicken Curry Bowl", 1499), ("Chickpea Chana Masala Bowl", 1199), ("Palak Paneer Bowl", 1399),
        ("Lentil Dal Bowl", 1099), ("Vegetable Biryani Bowl", 1299), ("Chicken Biryani Bowl", 1499),
        ("Garlic Naan 2pc", 499), ("Vegetable Samosa 2pc", 599), ("Cucumber Raita Cup", 349),
        ("Mango Lassi", 549), ("Masala Chai Cup", 399), ("Gulab Jamun 2pc", 499),
    ],
    "vietnamese_menu": [
        ("Beef Pho Noodle Bowl", 1499), ("Chicken Pho Noodle Bowl", 1399), ("Vegetable Pho Noodle Bowl", 1299),
        ("Grilled Pork Banh Mi", 999), ("Tofu Banh Mi", 899), ("Lemongrass Chicken Rice Bowl", 1399),
        ("Tofu Vermicelli Bowl", 1199), ("Fresh Summer Rolls 2pc", 699), ("Crispy Spring Rolls 3pc", 649),
        ("Vietnamese Iced Coffee", 499), ("Lemongrass Iced Tea", 449), ("Coconut Rice Pudding Cup", 499),
    ],
    "pet_accessories": [
        ("Adjustable Dog Harness", 1999), ("Retractable Dog Leash", 1799), ("Reflective Pet Collar", 999),
        ("Cat Scratching Pad", 1499), ("Foldable Pet Carrier", 3499), ("Stainless Pet Bowl", 1299),
        ("Pet Grooming Brush", 899), ("Pet Nail Clippers", 799), ("Washable Pet Bed", 3999),
        ("Pet Waste Bags 60pk", 699), ("Puzzle Treat Feeder", 1599), ("Collapsible Travel Pet Bowl", 999),
    ],
    "outdoor_gear": [
        ("Compact Camping Lantern", 2499), ("Foldable Camp Chair", 3999), ("Lightweight Daypack", 4999),
        ("Trekking Pole Pair", 3499), ("Insulated Picnic Bag", 2999), ("Camping Cookware Set", 4499),
        ("Dry Bag 10L", 1999), ("Hiking Compass", 1299), ("Emergency Rain Poncho", 899),
        ("Reflective Trail Vest", 1999), ("Camping Mug", 1299), ("Microfiber Travel Towel", 1499),
    ],
    "thai_menu": [
        ("Chicken Pad Thai Bowl", 1399), ("Tofu Pad Thai Bowl", 1299), ("Thai Green Curry Bowl", 1499),
        ("Thai Red Curry Bowl", 1499), ("Basil Chicken Rice Bowl", 1399), ("Pineapple Fried Rice Bowl", 1299),
        ("Tom Yum Soup Cup", 799), ("Thai Spring Rolls 3pc", 649), ("Satay Chicken Skewers 3pc", 899),
        ("Mango Sticky Rice", 699), ("Thai Iced Tea", 499), ("Coconut Iced Coffee", 549),
    ],
    "turkish_menu": [
        ("Chicken Doner Wrap", 1199), ("Falafel Doner Wrap", 1099), ("Lamb Kofte Plate", 1599),
        ("Spinach Gozleme", 999), ("Cheese Pide", 1299), ("Red Lentil Soup Cup", 699),
        ("Bulgur Pilaf Bowl", 899), ("Baklava 3pc", 649), ("Simit Bread", 399),
        ("Turkish Coffee Cup", 399), ("Apple Tea Cup", 449), ("Ayran Yogurt Drink", 449),
    ],
}
for _category, _products in _SPECIALTY.items():
    CATALOG[_category] = [CatalogItem(name, name, price) for name, price in _products]
    _label = _category.replace("_", " ").title()
    CATEGORY_LABELS[_category] = (_label, _label)

for _category, _rows in PRODUCTS.items():
    CATALOG[_category] = _items(_rows)
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


def catalog_slot_item(item: CatalogItem, currency: str) -> SlotItem:
    """Use the same product identity on templates and existing racks."""
    identity = json.dumps([item.en, item.ko, item.usd_cents], ensure_ascii=False, separators=(",", ":"))
    name, price = localized(item, currency)
    image = PACKSHOT_URLS.get(item.en)
    return SlotItem(sku=f"g_{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}", name=name, price=price, image_url=image)
