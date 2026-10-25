"""Short repeated labels must not expand into oversized downstream customer requests."""

import asyncio

import pytest
from pydantic import ValidationError

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize('field', ['keywords', 'person_types'])
@pytest.mark.parametrize('character', ['x', '주', '茶', '🛒'])
@pytest.mark.parametrize('length', [119, 120, 121])
def test_repeated_customer_inputs_have_the_same_label_bound(field, character, length):
    value = character * length
    schema = gen.TradeAreaProfile if field == 'keywords' else gen.HourlyProfile
    data = ({'keywords': [value], 'identities': ['resident'], 'purposes': ['groceries']} if field == 'keywords'
            else {'hour': 9, 'visitor_count': 5, 'person_types': [value]})
    if length > 120:
        with pytest.raises(ValidationError):
            schema.model_validate(data)
    else:
        assert getattr(schema.model_validate(data), field) == [value]
    output_schema = schema.model_json_schema()
    item_schema = output_schema['properties'][field]['items']
    if '$ref' in item_schema:
        item_schema = output_schema['$defs'][item_schema['$ref'].rsplit('/', 1)[1]]
    assert item_schema['maxLength'] == 120


@pytest.mark.parametrize('field', ['keywords', 'person_types'])
@pytest.mark.parametrize('character', ['nearby residents buying everyday groceries ', '동네 주민 장보기 ', '🛒'])
def test_repetitive_model_labels_are_corrected_before_customer_batches(field, character):
    class Model:
        corrections = 0
        writes = 0

        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if issubclass(schema, gen.PersonaBatch):
                self.writes += 1
                assert len(prompt) < 2000
                return schema(personas=[gen.GeneratedPersona(identity='resident', age_group='30s', gender='Female',
                    description='Offline shopper', intent='Buy groceries', purpose='groceries').model_dump()
                    for _ in range(prompt.count('\n['))])
            for attempt in range(kwargs['max_retries']):
                value = character * 500 if attempt == 0 else ('nearby' if field == 'keywords' else 'resident')
                data = ({'keywords': [value if field == 'keywords' else 'nearby'],
                         'identities': ['resident'], 'purposes': ['groceries']} if schema is gen.TradeAreaProfile
                        else {'hourly_profiles': [{'hour': 9, 'visitor_count': 5,
                                'person_types': [value if field == 'person_types' else 'resident']} ]})
                try:
                    return schema.model_validate(data)
                except ValidationError:
                    self.corrections += 1
            raise AssertionError('Label correction did not succeed')

    model = Model()
    people = asyncio.run(gen.generate_batched(model, 'offline', '동네 주민',
        [DaySchedule(day=1, open_hour=9, close_hour=10)], batch_size=5, seed=42))
    assert len(people) == 5 and len({p.id for p in people}) == 5
    assert model.corrections == 1 and model.writes == 1
    assert all(p.arrival_hour == 9 and not p.twin_of for p in people)
