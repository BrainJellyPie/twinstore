"""Additional generic starter products. Prices are illustrative USD cents."""

PRODUCTS: dict[str, list[tuple[str, str, int]]] = {
    "plant_based": [
        ("Barista Oat Milk 1L", "바리스타 귀리 음료 1L", 399), ("Unsweetened Almond Drink 1L", "무가당 아몬드 음료 1L", 349),
        ("Pea Protein Drink 330ml", "완두 단백질 음료 330ml", 329), ("Coconut Yogurt Cup", "코코넛 요거트 컵", 249),
        ("Smoked Tofu Slices", "훈제 두부 슬라이스", 449), ("Tempeh Block 200g", "템페 200g", 499),
        ("Plant Burger Patties 2pk", "식물성 버거 패티 2입", 699), ("Oat Cooking Cream 250ml", "귀리 요리 크림 250ml", 299),
        ("Cashew Cheese Spread", "캐슈 치즈 스프레드", 549), ("Chickpea Falafel Mix", "병아리콩 팔라펠 믹스", 399),
        ("Vegan Chocolate Pudding Cup", "비건 초콜릿 푸딩 컵", 279), ("Soy Protein Mince 200g", "콩 단백 다짐육 200g", 449),
    ],
    "breakfast_spreads": [
        ("Roasted Almond Butter 250g", "로스티드 아몬드 버터 250g", 799), ("Strawberry Preserve 200g", "딸기 잼 200g", 449),
        ("Crunchy Peanut Butter 340g", "크런치 땅콩 버터 340g", 399), ("Orange Marmalade 250g", "오렌지 마멀레이드 250g", 449),
        ("Wildflower Honey 250g", "야생화 꿀 250g", 699), ("Maple Syrup 250ml", "메이플 시럽 250ml", 899),
        ("Hazelnut Cocoa Spread 200g", "헤이즐넛 코코아 스프레드 200g", 499), ("Rolled Oats 500g", "압착 귀리 500g", 349),
        ("Cranberry Granola 350g", "크랜베리 그래놀라 350g", 549), ("Wholegrain Pancake Mix 400g", "통곡물 팬케이크 믹스 400g", 449),
        ("Chia Seed Pouch 200g", "치아씨드 200g", 599), ("Cinnamon Muesli 400g", "시나몬 뮤즐리 400g", 499),
    ],
    "home_coffee_tea": [
        ("Ceremonial Matcha Pouch 50g", "말차 가루 파우치 50g", 1199), ("House Roast Coffee Beans 250g", "하우스 로스트 원두 250g", 1299),
        ("Decaf Ground Coffee 250g", "디카페인 분쇄 커피 250g", 1199), ("Earl Grey Tea Bags 20pk", "얼그레이 티백 20입", 499),
        ("Chamomile Tea Bags 20pk", "캐모마일 티백 20입", 549), ("Hojicha Loose Tea 80g", "호지차 잎차 80g", 799),
        ("Vanilla Coffee Syrup 250ml", "바닐라 커피 시럽 250ml", 699), ("Paper Coffee Filters 100pk", "커피 종이 필터 100매", 399),
        ("Glass Pour Over Dripper", "유리 핸드드립 드리퍼", 1799), ("Bamboo Matcha Whisk", "대나무 말차 거품기", 1499),
        ("Reusable Tea Infuser", "재사용 차 인퓨저", 899), ("Double Wall Espresso Glass", "이중벽 에스프레소 잔", 999),
    ],
    "bath_body": [
        ("Gentle Botanical Hand Soap 300ml", "보태니컬 핸드솝 300ml", 649), ("Oat Body Wash 400ml", "귀리 바디워시 400ml", 899),
        ("Unscented Body Lotion 250ml", "무향 바디로션 250ml", 999), ("Shea Hand Cream 50ml", "시어 핸드크림 50ml", 499),
        ("Lavender Bath Salts 300g", "라벤더 배스솔트 300g", 799), ("Bamboo Cotton Swabs 200pk", "대나무 면봉 200개", 349),
        ("Reusable Cotton Rounds 8pk", "재사용 화장솜 8매", 899), ("Natural Loofah Sponge", "천연 수세미 스펀지", 399),
        ("Travel Shampoo Bar 60g", "여행용 샴푸바 60g", 699), ("Conditioner Bar 60g", "컨디셔너바 60g", 749),
        ("Soft Bath Towel", "부드러운 목욕 타월", 1499), ("Wooden Nail Brush", "원목 손톱 브러시", 499),
    ],
    "first_aid_tools": [
        ("Flexible Fabric Bandages 20pk", "신축성 패브릭 밴드 20매", 399), ("Compact Digital Thermometer", "소형 디지털 체온계", 1299),
        ("Sterile Gauze Pads 10pk", "멸균 거즈 패드 10매", 449), ("Medical Paper Tape Roll", "의료용 종이 테이프", 249),
        ("Elastic Support Bandage", "탄력 압박 붕대", 499), ("Reusable Hot Cold Pack", "재사용 냉온 찜질팩", 899),
        ("First Aid Scissors", "응급처치 가위", 699), ("Precision Tweezers", "정밀 핀셋", 499),
        ("Pocket First Aid Pouch", "휴대용 구급 파우치", 999), ("Nitrile Gloves 10pk", "니트릴 장갑 10매", 399),
        ("Saline Wound Wash 100ml", "상처 세척 식염수 100ml", 499), ("Digital Timer for Care", "돌봄용 디지털 타이머", 799),
    ],
    "nutrition_supplements": [
        ("Vitamin C Tablets 60ct", "비타민 C 정 60개", 999), ("Daily Multivitamin 30ct", "데일리 종합비타민 30개", 1299),
        ("Vitamin D Tablets 60ct", "비타민 D 정 60개", 1099), ("Magnesium Tablets 30ct", "마그네슘 정 30개", 1199),
        ("Plant Protein Powder 500g", "식물성 단백질 파우더 500g", 2499), ("Whey Protein Powder 500g", "유청 단백질 파우더 500g", 2699),
        ("Electrolyte Sachets 10pk", "전해질 분말 10포", 899), ("Fiber Powder 200g", "식이섬유 분말 200g", 1499),
        ("Probiotic Capsules 30ct", "프로바이오틱스 캡슐 30개", 1799), ("Omega 3 Capsules 60ct", "오메가 3 캡슐 60개", 1599),
        ("Collagen Powder 200g", "콜라겐 파우더 200g", 1999), ("Protein Snack Bites 100g", "단백질 스낵 바이트 100g", 499),
    ],
    "indoor_plants": [
        ("Terracotta Succulent Pot", "테라코타 다육식물 화분", 1299), ("Mini Snake Plant", "미니 산세베리아", 1499),
        ("Potted Golden Pothos", "골든 스킨답서스 화분", 1699), ("Small Peace Lily", "소형 스파티필룸", 1899),
        ("Potted Basil Herb", "바질 허브 화분", 699), ("Potted Rosemary Herb", "로즈메리 허브 화분", 799),
        ("Hanging Spider Plant", "행잉 접란 화분", 1599), ("Glass Plant Mister", "유리 식물 분무기", 999),
        ("Ceramic Planter Saucer", "세라믹 화분 받침", 499), ("Coco Coir Potting Block", "코코피트 블록", 599),
        ("Bamboo Plant Labels 12pk", "대나무 식물 이름표 12개", 399), ("Mini Pruning Snips", "미니 전정 가위", 899),
    ],
    "digital_accessories": [
        ("Braided Teal USB Cable 1m", "청록색 브레이드 USB 케이블 1m", 999), ("USB C Wall Charger 20W", "USB C 충전기 20W", 1499),
        ("Magnetic Cable Clips 6pk", "자석 케이블 클립 6개", 699), ("Foldable Phone Stand", "접이식 휴대폰 거치대", 899),
        ("Laptop Privacy Cover 3pk", "노트북 카메라 가리개 3개", 399), ("Screen Cleaning Kit", "화면 클리닝 키트", 799),
        ("Bluetooth Number Pad", "블루투스 숫자 키패드", 2499), ("Compact USB Hub 4 Port", "소형 USB 허브 4포트", 1999),
        ("Memory Card Case", "메모리 카드 케이스", 599), ("Silicone Earbud Case", "실리콘 이어버드 케이스", 799),
        ("Felt Laptop Sleeve 13in", "펠트 노트북 파우치 13인치", 1799), ("Desk Cable Organizer", "책상 케이블 정리함", 1299),
    ],
    "pet_enrichment": [
        ("Red Rubber Dog Chew Ring", "빨간 고무 강아지 치발 링", 899), ("Cat Feather Wand", "고양이 깃털 낚싯대", 599),
        ("Snuffle Mat for Dogs", "강아지 노즈워크 매트", 2499), ("Treat Puzzle Ball", "간식 퍼즐 공", 1299),
        ("Catnip Mouse Toy 3pk", "캣닢 쥐 장난감 3개", 699), ("Crinkle Cat Tunnel", "바스락 고양이 터널", 1999),
        ("Rope Tug Toy", "로프 터그 장난감", 799), ("Slow Feeding Pet Mat", "반려동물 슬로 피딩 매트", 1499),
        ("Bird Foraging Toy", "새 먹이 찾기 장난감", 999), ("Rabbit Chew Sticks 10pk", "토끼 이갈이 스틱 10개", 499),
        ("Floating Fetch Toy", "물놀이 가져오기 장난감", 1099), ("Training Clicker", "반려동물 훈련 클리커", 399),
    ],
    "picnic_reusables": [
        ("Green Handle Camping Mug", "초록 손잡이 캠핑 머그", 1299), ("Bamboo Cutlery Set", "대나무 커트러리 세트", 899),
        ("Stainless Drinking Straws 4pk", "스테인리스 빨대 4개", 799), ("Beeswax Food Wraps 3pk", "밀랍 식품 랩 3매", 1199),
        ("Silicone Sandwich Pouch", "실리콘 샌드위치 파우치", 999), ("Insulated Lunch Jar 400ml", "보온 도시락 병 400ml", 2499),
        ("Collapsible Food Container", "접이식 식품 용기", 1499), ("Cotton Picnic Blanket", "면 피크닉 담요", 2999),
        ("Reusable Ice Pack Pair", "재사용 아이스팩 2개", 699), ("Enamel Picnic Plate", "에나멜 피크닉 접시", 999),
        ("Foldable Shopping Tote", "접이식 장바구니", 799), ("Wide Mouth Water Flask 750ml", "넓은 입구 물병 750ml", 2299),
    ],
    "artisan_snacks": [
        ("Butter Croissant Bag 2pk", "버터 크루아상 봉지 2입", 499), ("Sea Salt Sweet Potato Chips", "씨솔트 고구마칩", 349),
        ("Rosemary Sourdough Crackers", "로즈메리 사워도우 크래커", 399), ("Dark Chocolate Almonds 100g", "다크초콜릿 아몬드 100g", 449),
        ("Dried Mango Strips 100g", "건망고 스트립 100g", 399), ("Sesame Seed Brittle 80g", "참깨 강정 80g", 299),
        ("Coconut Crisps 60g", "코코넛 칩 60g", 279), ("Baked Lentil Chips 90g", "구운 렌틸칩 90g", 329),
        ("Pistachio Biscotti 4pk", "피스타치오 비스코티 4개", 449), ("Mini Olive Focaccia", "미니 올리브 포카치아", 399),
        ("Apple Cinnamon Fruit Leather", "사과 시나몬 과일 롤", 199), ("Smoked Paprika Chickpeas 100g", "훈연 파프리카 병아리콩 100g", 349),
    ],
    "craft_refreshments": [
        ("Glass Bottle Lemon Sparkling Water", "유리병 레몬 탄산수", 249), ("Blood Orange Soda 330ml", "블러드오렌지 소다 330ml", 299),
        ("Grapefruit Rosemary Soda 330ml", "자몽 로즈메리 소다 330ml", 329), ("Hibiscus Iced Tea 300ml", "히비스커스 아이스티 300ml", 279),
        ("Peach Oolong Tea 300ml", "복숭아 우롱차 300ml", 299), ("Cucumber Mint Sparkling Water", "오이 민트 탄산수", 279),
        ("Apple Ginger Juice 250ml", "사과 생강 주스 250ml", 349), ("Pomegranate Juice 250ml", "석류 주스 250ml", 399),
        ("Yuzu Honey Drink 300ml", "유자 꿀 음료 300ml", 329), ("Passionfruit Soda 330ml", "패션프루트 소다 330ml", 299),
        ("Cold Brew Rooibos 300ml", "콜드브루 루이보스 300ml", 279), ("Still Water Glass Bottle 500ml", "유리병 생수 500ml", 199),
    ],
}

PACKSHOTS = [
    "Barista Oat Milk 1L", "Roasted Almond Butter 250g", "Ceremonial Matcha Pouch 50g", "House Roast Coffee Beans 250g",
    "Gentle Botanical Hand Soap 300ml", "Flexible Fabric Bandages 20pk", "Vitamin C Tablets 60ct", "Compact Digital Thermometer",
    "Terracotta Succulent Pot", "Braided Teal USB Cable 1m", "Red Rubber Dog Chew Ring", "Green Handle Camping Mug",
    "Butter Croissant Bag 2pk", "Glass Bottle Lemon Sparkling Water", "Sea Salt Sweet Potato Chips", "Strawberry Preserve 200g",
]

PACKSHOT_SHEETS = {
    "starter-01": PACKSHOTS,
    "starter-02": [
        "Cola 500ml", "Milk 1L", "Potato Chips Original", "Spicy Cup Ramen",
        "Croissant", "Greek Yogurt Cup", "Chocolate Cookies", "Tuna Can",
        "Bananas", "Apples 2pk", "Tofu", "Eggs 10pk",
        "Dish Soap", "Tissues", "Sunscreen SPF50", "Paper Towels",
    ],
}
PACKSHOT_URLS = {name: f"/api/catalog-images/{sheet}/{index}.webp"
                 for sheet, names in PACKSHOT_SHEETS.items() for index, name in enumerate(names)}
