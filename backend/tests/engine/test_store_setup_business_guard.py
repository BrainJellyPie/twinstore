"""A small business-type check repairs incompatible layouts without reselecting compatible ones."""

import asyncio

import pytest
from instructor.core.exceptions import IncompleteOutputException

from store_emulator.engine.generators.store_setup_writer import draft_store_setup


FORMATS = [
    ("corner", "Corner store", "convenience", "A small neighborhood shop"),
    ("bakery", "Bakery", "bakery", "Fresh bread and pastries"),
    ("artisan", "Artisan bakery", "bakery", "Bread displays and seating"),
]
FACTS = {"name": "Bread Shop", "description": "A local bakery", "address": "Seoul",
         "open_days": "weekend", "open_hour": 10, "close_hour": 18, "currency": "KRW", "rationale": "Owner details"}


class Model:
    def __init__(self, business="bakery", initial="corner", repair="artisan", cutoff=None):
        self.business, self.initial, self.repair, self.cutoff = business, initial, repair, cutoff
        self.calls = []
        self.failed = False
        self.formats = 0

    async def generate_structured_async(self, schema, system, user, **kwargs):
        stage = "facts" if "open_hour" in schema.model_fields else "business" if "store_type" in schema.model_fields else "format"
        self.calls.append((stage, schema, system, user, kwargs))
        if self.cutoff == stage and not self.failed:
            self.failed = True
            raise IncompleteOutputException("cut off")
        if stage == "facts": return schema.model_validate(FACTS)
        if stage == "business":
            return schema.model_validate({} if self.business == "omitted" else {"store_type": self.business})
        self.formats += 1
        return schema.model_validate({"format": self.initial if self.formats == 1 else self.repair})


@pytest.mark.parametrize("business", ["bakery", " BAKERY ", '"bakery"'])
@pytest.mark.parametrize("initial", ["corner", "", "unlisted"])
def test_incompatible_layout_is_repaired_with_only_matching_formats_and_facts_preserved(business, initial):
    model = Model(business, initial=initial)
    result = asyncio.run(draft_store_setup(model, "동네 빵집", FORMATS, "ko"))
    assert [call[0] for call in model.calls] == ["facts", "format", "business", "format"]
    assert (result.template_id, result.store_type) == ("artisan", "bakery")
    assert all(getattr(result, key) == value for key, value in FACTS.items())
    assert not result.warnings
    business_wire = model.calls[2][1].model_json_schema()
    assert business_wire["required"] == ["store_type"]
    assert business_wire["properties"]["store_type"]["enum"] == ["bakery", "convenience"]
    repaired = model.calls[-1]
    assert repaired[1].model_json_schema()["properties"]["format"]["enum"] == ["bakery", "artisan"]
    assert "corner:" not in repaired[3] and "Fresh bread and pastries" in repaired[3]


@pytest.mark.parametrize("initial", ["bakery", "artisan", "Artisan bakery"])
def test_a_compatible_specific_layout_is_kept(initial):
    model = Model(initial=initial, repair="corner")
    result = asyncio.run(draft_store_setup(model, "Bakery with seating", FORMATS))
    assert result.template_id == ("bakery" if initial == "bakery" else "artisan")
    assert [call[0] for call in model.calls] == ["facts", "format", "business"]


@pytest.mark.parametrize("business", ["", None, "omitted", "invented", "bakery or convenience"])
def test_unusable_business_label_keeps_the_original_layout(business):
    model = Model(business)
    result = asyncio.run(draft_store_setup(model, "Local shop", FORMATS))
    assert result.template_id == "corner"
    assert len(model.calls) == 3


def test_non_enforcing_provider_cannot_repair_with_a_layout_of_another_business():
    model = Model(repair="corner")
    result = asyncio.run(draft_store_setup(model, "Bakery", FORMATS))
    assert not result.template_id and not result.store_type and result.warnings
    assert result.name == FACTS["name"]


def test_business_cutoff_has_one_bounded_expansion_and_does_not_repeat_facts():
    model = Model(cutoff="business")
    result = asyncio.run(draft_store_setup(model, "Bakery", FORMATS))
    assert result.template_id == "artisan"
    assert [call[4]["max_tokens"] for call in model.calls] == [900, 160, 160, 320, 160]
    assert model.calls[2][2:4] == model.calls[3][2:4]


@pytest.mark.parametrize("formats", [[], FORMATS[:1], FORMATS[1:]])
def test_zero_or_one_business_type_does_not_add_a_classification_request(formats):
    model = Model(initial="bakery" if formats == FORMATS[1:] else "corner")
    asyncio.run(draft_store_setup(model, "Shop", formats))
    assert [call[0] for call in model.calls] == ["facts", "format"]
