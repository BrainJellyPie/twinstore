from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.layout_gen.catalog_expansion import PACKSHOTS, PRODUCTS


@pytest.fixture
def client():
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("index,name", enumerate(PACKSHOTS))
def test_bundled_packshots_are_local_decodable_and_used_in_all_currencies(client, index, name):
    product = next(p for values in CATALOG.values() for p in values if p.en == name)
    urls = {catalog_slot_item(product, currency).image_url for currency in ["USD", "KRW", "JPY"]}
    assert urls == {f"/api/catalog-images/starter-01/{index}.webp"}
    result = client.get(next(iter(urls)))
    assert result.status_code == 200 and result.headers["content-type"] == "image/webp"
    assert "immutable" in result.headers["cache-control"]
    with Image.open(BytesIO(result.content)) as image:
        assert min(image.size) >= 200
        assert image.getextrema() != ((255, 255),) * 3
    assert client.get(next(iter(urls))).content == result.content


@pytest.mark.parametrize("path", ["starter-01/-1", "starter-01/16", "starter-01/99999999", "unknown/0", "../0", "starter-01/1.5", "starter-01/NaN"])
def test_unknown_image_cannot_read_arbitrary_files(client, path):
    assert client.get(f"/api/catalog-images/{path}.webp").status_code in {404, 422}


@pytest.mark.parametrize("category", PRODUCTS)
def test_new_categories_have_twelve_distinct_priced_localized_products(category):
    rows = CATALOG[category]
    assert len(rows) == 12
    assert len({p.en for p in rows}) == len({p.ko for p in rows}) == 12
    assert all(p.usd_cents > 0 and p.ko != p.en for p in rows)
    assert len({catalog_slot_item(p, "USD").sku for p in rows}) == 12
