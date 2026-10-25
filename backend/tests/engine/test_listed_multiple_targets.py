"""Several distinct names in one model field must not select the longest one."""

import pytest

from store_emulator.domain.rack import SlotItem
from store_emulator.engine.generators.store_setup_writer import _Setup, to_setup
from store_emulator.engine.layout_brief import _Brief, to_options
from store_emulator.engine.marketing.shelf_test_design import _Draft, to_design
from store_emulator.engine.prompting import resolve_listed
from tests.engine.test_shelf_design_boundaries import store


@pytest.mark.parametrize("asked,names,expected", [
    ("Tea or Premium Coffee", {"tea": {"tea"}, "premium coffee": {"coffee"}}, None),
    ("Tea Extra then Tea", {"tea": {"tea"}, "tea extra": {"extra"}}, None),
    ("Green Tea Classic", {"green tea": {"green"}, "tea classic": {"classic"}}, None),
    ("녹차 또는 프리미엄 홍차", {"녹차": {"green"}, "프리미엄 홍차": {"black"}}, None),
    ('"Tea Extra", on Drinks', {"tea": {"tea"}, "tea extra": {"extra"}}, {"extra"}),
    ("Tea Extra then Tea Extra", {"tea": {"tea"}, "tea extra": {"extra"}}, {"extra"}),
    ("Tea or Premium Coffee", {"tea": {"same"}, "premium coffee": {"same"}}, {"same"}),
    ("Green Tea Classic", {"green tea": {"green"}, "tea classic": {"classic"}, "green tea classic": {"full"}}, {"full"}),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_distinct_mentions_are_ambiguous_but_nested_names_and_aliases_still_resolve(asked, names, expected, reverse):
    assert resolve_listed(asked, dict(reversed(list(names.items()))) if reverse else names) == expected


@pytest.mark.parametrize("reverse", [False, True])
def test_ambiguous_drafts_cannot_change_a_different_product_format_or_category(reverse):
    source = store()
    source.racks[0].slots[0].items.append(SlotItem(sku="coffee", name="Premium Coffee", price=349))
    if reverse:
        source.racks[0].slots[0].items.reverse()
    before = source.model_dump_json()
    with pytest.raises(ValueError):
        to_design(_Draft(name="Price", product="Tea or Premium Coffee", price=0.99), source, "USD", [])
    formats = [("tea", "Tea", "convenience"), ("coffee", "Premium Coffee", "cafe")]
    categories = [("tea", "Tea"), ("coffee", "Premium Coffee")]
    if reverse:
        formats.reverse()
        categories.reverse()
    setup = to_setup(_Setup(name="My store", format="Tea or Premium Coffee"), formats)
    assert setup.name == "My store" and setup.template_id == setup.store_type == "" and setup.warnings
    brief = to_options(_Brief(excluded_categories=["Tea or Premium Coffee"], checkouts=2), {}, categories)
    assert brief.options == {"checkouts": 2} and brief.warnings
    assert source.model_dump_json() == before
