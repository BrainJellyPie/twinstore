"""Interior color choices change finishes without changing stock or circulation."""
import pytest
from pydantic import ValidationError
from store_emulator.domain.layout_options import InteriorColors, LayoutOptions
from store_emulator.domain.store import Store
from store_emulator.engine.layout_gen import TEMPLATES, generate_store
from store_emulator.engine.validation import validate

@pytest.mark.parametrize("template", [template.id for template in TEMPLATES])
@pytest.mark.parametrize("colors", [
    {"wall": "#000000", "floor": "#FFFFFF", "accent": "#Aa00Ff", "counter": "#123456"},
    {"wall": None, "floor": "#000000", "accent": None, "counter": "#FFFFFF"},
])
def test_every_format_keeps_geometry_stock_hours_and_independent_colors(template, colors):
    baseline = generate_store(template, seed=7, currency="JPY")
    custom = generate_store(template, seed=7, currency="JPY", options=LayoutOptions(design_colors=InteriorColors.model_validate(colors)))
    assert validate(custom) == []
    assert custom.model_dump(exclude={"design_colors"}) == baseline.model_dump(exclude={"design_colors"})
    assert custom.design_colors.model_dump() == {key: value.lower() if value else None for key, value in colors.items()}
    assert baseline.design_colors is None
    assert Store.model_validate_json(custom.model_dump_json()) == custom

@pytest.mark.parametrize("key", ["wall", "floor", "accent", "counter"])
@pytest.mark.parametrize("invalid", [True, 123456, 1.2, [], {}, "", "red", "#fff", "#12345678", "123456", "#gg0000", " #123456", "#123456\n", "#１２３４５６", "rgb(0,0,0)"])
def test_reject_invalid_colors_in_layout_options_and_saved_stores(key, invalid):
    for model, payload in [(LayoutOptions, {}), (Store, {"id": "a", "name": "A", "type": "store", "grid_size": [8, 6]})]:
        with pytest.raises(ValidationError):
            model.model_validate({**payload, "design_colors": {key: invalid}})

@pytest.mark.parametrize("colors", [None, {}, {"wall": None}, {"wall": None, "floor": None, "accent": None, "counter": None}])
def test_default_and_null_colors_keep_legacy_stores_valid(colors):
    legacy = {"id": "legacy", "name": "Legacy", "type": "store", "grid_size": [8, 6]}
    assert Store.model_validate(legacy).design_colors is None
    assert Store.model_validate({**legacy, "design_colors": colors}).design_theme == "classic"
    assert LayoutOptions.model_validate({"design_colors": colors}).design_theme is None

@pytest.mark.parametrize("colors", [{"ceiling": "#ffffff"}, {"Wall": "#ffffff"}, [], "#ffffff", True])
def test_reject_unknown_channels_and_non_objects(colors):
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate({"design_colors": colors})
