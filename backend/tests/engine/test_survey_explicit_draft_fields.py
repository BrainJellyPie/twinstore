"""A grammar-guided draft must explicitly choose images, price and quotas."""

import pytest
from jsonschema import Draft202012Validator

from store_emulator.engine.marketing.survey_design import _Draft, to_design


def complete_draft():
    return {
        "name": "Two tea packs", "images": ["Classic", "New"],
        "questions": ["purchase_intent", "value", "preference", "open"],
        "context": "Compare these packs.", "reference_price": 0,
        "age_groups": ["20s"], "genders": ["Female"], "rationale": "Compare the requested packs.",
    }


@pytest.mark.parametrize("field", ["images", "context", "reference_price", "age_groups", "genders", "rationale"])
def test_wire_grammar_cannot_silently_omit_requested_draft_fields(field):
    payload = complete_draft()
    validator = Draft202012Validator(_Draft.model_json_schema())
    assert validator.is_valid(payload)
    del payload[field]
    assert not validator.is_valid(payload)


@pytest.mark.parametrize("price", [0, None, 2.5])
def test_explicit_prices_and_ordered_images_survive_conversion_and_cache_roundtrip(price):
    payload = complete_draft()
    payload["reference_price"] = price
    Draft202012Validator(_Draft.model_json_schema()).validate(payload)
    draft = _Draft.model_validate(payload)
    assert _Draft.model_validate_json(draft.model_dump_json()) == draft
    result = to_design(draft, [("Classic", "classic"), ("New", "new")], "USD")
    assert result.stimuli == ["classic", "new"] and not result.warnings
    assert result.reference_price == (None if price is None else int(price * 100))
    assert result.age_groups == ["20s"] and result.genders == ["Female"]
    assert "preference" in result.questions


def test_older_partial_drafts_keep_runtime_defaults():
    draft = _Draft.model_validate({"name": "Legacy", "questions": ["appeal"]})
    assert draft.images == [] and draft.reference_price is None
    assert draft.age_groups == [] and draft.genders == []
    assert _Draft.model_validate_json(draft.model_dump_json()) == draft


def test_explicit_unknowns_are_valid_without_inventing_a_price_or_quota():
    payload = complete_draft()
    payload.update(images=[], reference_price=None, age_groups=[], genders=[], context="", rationale="")
    Draft202012Validator(_Draft.model_json_schema()).validate(payload)
    result = to_design(_Draft.model_validate(payload), [], "KRW")
    assert result.reference_price is None and result.age_groups == [] and result.genders == []
