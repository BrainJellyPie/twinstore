from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.layout_gen.catalog_expansion import PACKSHOT_SHEETS, PRODUCTS


@pytest.fixture
def client():
    from store_emulator.server.main import app
    return TestClient(app)


@pytest.mark.parametrize("sheet,index,name", [(sheet, index, name) for sheet, names in PACKSHOT_SHEETS.items() for index, name in enumerate(names)])
def test_bundled_packshots_are_local_decodable_and_used_in_all_currencies(client, sheet, index, name):
    product = next(p for values in CATALOG.values() for p in values if p.en == name)
    urls = {catalog_slot_item(product, currency).image_url for currency in ["USD", "KRW", "JPY"]}
    assert urls == {f"/api/catalog-images/{sheet}/{index}.webp"}
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


@pytest.mark.parametrize("sheet", PACKSHOT_SHEETS)
@pytest.mark.parametrize("index", [-1, 16, 1000000])
def test_each_sheet_rejects_out_of_range_cells(client, sheet, index):
    assert client.get(f"/api/catalog-images/{sheet}/{index}.webp").status_code == 404


def test_packshot_manifest_has_unique_cells_and_existing_products():
    from store_emulator.application.catalog_images import ROW_BOUNDS
    names = [name for values in PACKSHOT_SHEETS.values() for name in values]
    assert len(names) == len(set(names))
    assert set(ROW_BOUNDS) == set(PACKSHOT_SHEETS)
    for sheet, products in PACKSHOT_SHEETS.items():
        assert len(products) == 16 and len(ROW_BOUNDS[sheet]) == 5
        assert tuple(sorted(set(ROW_BOUNDS[sheet]))) == ROW_BOUNDS[sheet]
        assert ROW_BOUNDS[sheet][0] == 0 and ROW_BOUNDS[sheet][-1] == 1
    for name in names:
        assert any(p.en == name for values in CATALOG.values() for p in values)


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
def test_same_named_variants_share_generic_photo_without_merging_identity_or_price(currency):
    products = [catalog_slot_item(p, currency) for values in CATALOG.values() for p in values if p.en == "Sunscreen SPF50"]
    assert len(products) == len({p.sku for p in products}) == len({p.price for p in products}) == 2
    assert {p.image_url for p in products} == {"/api/catalog-images/starter-02/14.webp"}
