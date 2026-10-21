"""An accepted category selection must not silently produce an empty store."""
import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine.layout_gen import generate_store, get_template


def options(style):
    template = get_template("urban_cvs")
    categories = set(template.fridges + template.freezers + template.wall_shelves + template.gondolas + template.near_counter)
    return {"width": 8, "height": 6, "aisle_width": 4, "dining_tables": 0, "style": style,
            "excluded_categories": sorted(categories - {"chips"})}


@pytest.mark.parametrize("style", ["spine", "cross"])
def test_selected_category_must_fit_somewhere(style):
    with pytest.raises(ValueError, match="No products.*fit"):
        generate_store("urban_cvs", options=LayoutOptions(**options(style)))


@pytest.mark.parametrize("style", ["aisles", "perimeter"])
def test_single_category_is_accepted_when_it_fits(style):
    store = generate_store("urban_cvs", options=LayoutOptions(**options(style)))
    assert store.product_racks
    assert {rack.rack_desc for rack in store.product_racks} == {"chips"}


@pytest.mark.parametrize("operation", ["preview", "preset", "save"])
@pytest.mark.parametrize("style", ["spine", "cross"])
def test_empty_selected_assortment_is_rejected_before_saving(tmp_path, monkeypatch, operation, style):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"name": "Test", "currency": "USD"})
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    from store_emulator.server.main import app
    client = TestClient(app, raise_server_exceptions=False)
    layout = {"template_id": "urban_cvs", **options(style)}
    if operation == "preview":
        response = client.post("/api/store-templates/preview", json=layout)
    elif operation == "preset":
        response = client.post("/api/store-templates/preset/validate", json={"format": "twinstore-layout-options", "version": 1, "layout": layout})
    else:
        response = client.post("/api/projects/proj_test/setups/generate", json=layout)
    assert response.status_code == 422, response.text
    assert "No products" in response.json()["detail"]
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
