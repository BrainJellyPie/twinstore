"""Model drafts normalize levels using the same equality as a fieldable conjoint study."""
import pytest

from store_emulator.domain.marketing import ConjointRequest
from store_emulator.engine.marketing.conjoint_design import _Draft, to_design


@pytest.mark.parametrize(('levels', 'expected'), [
    (['Regular', 'regular', 'Zero'], ['Regular', 'Zero']),
    ([' Regular ', 'REGULAR', 'Zero', ' zero '], ['Regular', 'Zero']),
    (['Straße', 'STRASSE', 'Andere'], ['Straße', 'Andere']),
    (['a' * 60 + '1', 'A' * 60 + '2', 'Short'], ['a' * 60, 'Short']),
])
def test_equivalent_levels_are_deduplicated_without_losing_the_other_options(levels, expected):
    draft = _Draft.model_validate({'name': 'Study', 'product': 'Tea', 'attributes': [{'name': 'Style', 'levels': levels}], 'prices': [1.49, 1.99]})
    before = draft.model_dump()
    design = to_design(draft, 'USD', [])
    assert design.attributes[0].levels == expected
    ConjointRequest.model_validate(design.model_dump())
    assert draft.model_dump() == before


@pytest.mark.parametrize('levels', [['Regular', 'regular'], ['Straße', 'STRASSE'], [' A ', 'a']])
def test_an_attribute_with_one_distinct_level_is_dropped_while_the_rest_remains(levels):
    draft = _Draft.model_validate({'name': 'Study', 'product': 'Tea', 'attributes': [
        {'name': 'Style', 'levels': levels}, {'name': 'Size', 'levels': ['Small', 'Large']},
    ], 'prices': [1.49, 1.99]})
    design = to_design(draft, 'USD', [])
    assert [a.name for a in design.attributes] == ['Size']
    ConjointRequest.model_validate(design.model_dump())


def test_a_draft_with_no_distinct_attribute_still_reports_a_clear_error():
    draft = _Draft.model_validate({'name': 'Study', 'product': 'Tea', 'attributes': [{'name': 'Style', 'levels': ['A', 'a']}], 'prices': [1, 2]})
    with pytest.raises(ValueError, match='no usable attribute'):
        to_design(draft, 'USD', [])
