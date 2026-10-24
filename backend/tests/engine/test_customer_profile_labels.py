"""Trade-area labels must fit the customer schema that must repeat them verbatim."""

import asyncio

import pytest
from pydantic import ValidationError

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("field", ["identity", "purpose"])
@pytest.mark.parametrize("character", ["x", "상", "茶", "🛒"])
@pytest.mark.parametrize("length", [119, 120, 121])
def test_profile_labels_match_the_customer_schema_limits(field, character, length):
    values = {"identity": "shopper", "purpose": "snack", field: character * length}
    data = {"keywords": ["nearby"], "identities": [values["identity"]], "purposes": [values["purpose"]]}
    if length > 120:
        with pytest.raises(ValidationError):
            gen.TradeAreaProfile.model_validate(data)
    else:
        profile = gen.TradeAreaProfile.model_validate(data)
        person = gen.GeneratedPersona(identity=profile.identities[0], purpose=profile.purposes[0],
            age_group="20s", gender="Female", description="offline", intent="snack")
        assert getattr(person, field) == character * length


@pytest.mark.parametrize("field", ["identity", "purpose"])
@pytest.mark.parametrize("character", ["x", "상", "茶", "🛒"])
def test_profile_correction_happens_before_customer_batches_are_sent(field, character):
    class Model:
        profile_attempts = 0
        customer_calls = 0
        labels = {"identity": "shopper", "purpose": "snack"}

        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if schema is gen.TradeAreaProfile:
                # Offline structured-response retry: the schema must reject the incompatible first answer.
                for attempt in range(kwargs["max_retries"]):
                    self.profile_attempts += 1
                    labels = {**self.labels, field: character * (121 if attempt == 0 else 120)}
                    try:
                        result = schema(keywords=["nearby"], identities=[labels["identity"]], purposes=[labels["purpose"]])
                    except ValidationError:
                        continue
                    self.labels = labels
                    return result
                raise AssertionError("Profile correction failed")
            if issubclass(schema, gen.DailyTrafficResult):
                return schema(hourly_profiles=[gen.HourlyProfile(hour=9, visitor_count=20, person_types=[self.labels["identity"]])])
            self.customer_calls += 1
            return gen.PersonaBatch(personas=[gen.GeneratedPersona(**self.labels, age_group="20s", gender="Female",
                description="offline", intent="snack") for _ in range(prompt.count("\n["))])

    model = Model()
    people = asyncio.run(gen.generate_batched(model, "offline", "offline", [DaySchedule(day=1, open_hour=9, close_hour=10)]))
    assert model.profile_attempts == 2 and model.customer_calls == 2
    assert len(people) == 20
    assert all(getattr(person, field) == character * 120 for person in people)
