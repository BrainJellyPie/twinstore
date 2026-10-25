"""Valid summaries with absent optional details persist as ordinary text fields."""

from store_emulator.application import marketing, study_reading
from store_emulator.application.storage.io import read_json
from tests.server.test_study_commentary_lifecycle import study


def test_optional_null_details_do_not_fail_or_leak_into_saved_commentary(study, monkeypatch):
    client, kind, folder, url = study
    suffix = "narrative" if kind == "experiment" else "reading"
    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            return schema.model_validate({"summary": "There is no clear winner.", "interpretation": None, "next_steps": None})
    for module in (marketing, study_reading):
        monkeypatch.setattr(module, "assistive_client", lambda *args, **kwargs: Model())
    result = client.post(f"{url}/{suffix}", json={})
    assert result.status_code == 200, result.text
    assert result.json()["summary"] == "There is no clear winner."
    assert result.json()["interpretation"] == result.json()["next_steps"] == ""
    assert read_json(folder / f"{suffix}.json") == result.json()
