"""One active commentary writer owns the result until it succeeds or fails."""

import pytest

from store_emulator.application import marketing, study_reading
from store_emulator.application.storage.io import write_json
from store_emulator.engine.marketing.reading import StudyReading
from store_emulator.engine.marketing.report import ReportNarrative
from tests.server.test_study_commentary_lifecycle import study


@pytest.mark.parametrize("operation", ["clear", "rewrite"])
@pytest.mark.parametrize("existing", [False, True])
def test_active_commentary_is_not_cleared_or_overwritten(study, monkeypatch, operation, existing):
    client, kind, folder, url = study
    suffix = "narrative" if kind == "experiment" else "reading"
    path = folder / f"{suffix}.json"
    if existing:
        write_json(path, {"summary": "Saved earlier result", "interpretation": "", "next_steps": ""})
    before = path.read_bytes() if existing else None
    calls, seen = [], {}

    async def generate(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            response = client.delete(f"{url}/{suffix}") if operation == "clear" else client.post(f"{url}/{suffix}", json={})
            seen["status"] = response.status_code
            seen["unchanged"] = (path.read_bytes() if path.exists() else None) == before
        schema = ReportNarrative if kind == "experiment" else StudyReading
        return schema(summary="Finished current commentary", interpretation="", next_steps="")

    monkeypatch.setattr(marketing, "write_narrative", generate)
    monkeypatch.setattr(study_reading, "read_study", generate)
    result = client.post(f"{url}/{suffix}", json={})
    assert result.status_code == 200, result.text
    assert seen == {"status": 409, "unchanged": True} and len(calls) == 1
    assert "Finished current commentary" in path.read_text()
    assert client.delete(f"{url}/{suffix}").status_code == 204 and not path.exists()
    assert client.post(f"{url}/{suffix}", json={}).status_code == 200 and len(calls) == 2


def test_failed_provider_releases_commentary_for_manual_retry(study, monkeypatch):
    client, kind, folder, url = study
    suffix = "narrative" if kind == "experiment" else "reading"
    calls = []

    async def generate(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("provider offline")
        schema = ReportNarrative if kind == "experiment" else StudyReading
        return schema(summary="Retry succeeded", interpretation="", next_steps="")

    monkeypatch.setattr(marketing, "write_narrative", generate)
    monkeypatch.setattr(study_reading, "read_study", generate)
    assert client.post(f"{url}/{suffix}", json={}).status_code == 502
    assert not (folder / f"{suffix}.json").exists()
    assert client.post(f"{url}/{suffix}", json={}).status_code == 200
    assert client.delete(f"{url}/{suffix}").status_code == 204


def test_clearing_missing_study_reports_not_found(study):
    client, kind, folder, url = study
    suffix = "narrative" if kind == "experiment" else "reading"
    assert client.delete(url).status_code == 204
    assert client.delete(f"{url}/{suffix}").status_code == 404
    assert not folder.exists()
