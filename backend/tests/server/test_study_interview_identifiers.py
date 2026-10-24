"""New neighborhood studies and interviews must preserve earlier saved records."""

from itertools import count
from types import SimpleNamespace
from uuid import UUID

import pytest

from store_emulator.application import interview, town_synergy
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from tests.server.test_interview_project_lifecycle import RUN, conversation, send  # noqa: F401
from tests.server.test_simulation_setup_races import PID, layout  # noqa: F401
from tests.server.test_synergy_start_snapshot import study  # noqa: F401

IDENTIFIER = UUID("abcdef00-0000-4000-8000-000000000001")


def distinct(monkeypatch, module):
    sequence = count(IDENTIFIER.int)
    monkeypatch.setattr(module, "uuid", SimpleNamespace(uuid4=lambda: UUID(int=next(sequence))))


def test_neighborhood_studies_with_matching_uuid_prefixes_keep_both_results(study, monkeypatch):
    _, submit, start = study
    distinct(monkeypatch, town_synergy)
    first = start()
    assert first.status_code == 200, first.text
    root = metadata_path(PID).parent / "synergy"
    old = root / first.json()["job_id"]
    before = (old / "status.json").read_bytes()
    second = start()
    assert second.status_code == 200, second.text
    assert (old / "status.json").read_bytes() == before
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(town_synergy.list_synergy_jobs(PID)) == 2
    assert submit.call_count == 2


@pytest.mark.parametrize("legacy", [False, True])
def test_neighborhood_existing_identifier_is_isolated_and_remains_readable(study, monkeypatch, legacy):
    _, submit, start = study
    monkeypatch.setattr(town_synergy, "uuid", SimpleNamespace(uuid4=lambda: IDENTIFIER))
    first = start()
    assert first.status_code == 200, first.text
    original = first.json()
    root = metadata_path(PID).parent / "synergy"
    identifier = "syn_abcdef" if legacy else f"syn_{IDENTIFIER.hex}"
    old = root / identifier
    source = root / original["job_id"]
    if source != old:
        source.rename(old)
    write_json(old / "status.json", {**original, "job_id": identifier})
    before = (old / "status.json").read_bytes()
    second = start()
    assert (old / "status.json").read_bytes() == before
    assert second.status_code == (200 if legacy else 409), second.text
    assert submit.call_count == (2 if legacy else 1)
    assert town_synergy.get_synergy_job(PID, identifier).status.job_id == identifier


def test_group_interviews_with_matching_uuid_prefixes_keep_both_transcripts(conversation, monkeypatch):
    client, shopper, base = conversation
    distinct(monkeypatch, interview)
    first = send(client, shopper, "group")
    assert first.status_code == 200, first.text
    old = base / "group_interviews" / f"{first.json()['group_id']}.json"
    before = old.read_bytes()
    second = send(client, shopper, "group")
    assert second.status_code == 200, second.text
    assert old.read_bytes() == before
    assert first.json()["group_id"] != second.json()["group_id"]
    assert len(interview.list_group_interviews(PID, RUN)) == 2


@pytest.mark.parametrize("legacy", [False, True])
def test_group_existing_identifier_is_isolated_and_remains_readable(conversation, monkeypatch, legacy):
    client, shopper, base = conversation
    monkeypatch.setattr(interview, "uuid", SimpleNamespace(uuid4=lambda: IDENTIFIER))
    first = send(client, shopper, "group")
    assert first.status_code == 200, first.text
    original = first.json()
    identifier = "grp_abcdef" if legacy else f"grp_{IDENTIFIER.hex}"
    old = base / "group_interviews" / f"{identifier}.json"
    source = base / "group_interviews" / f"{original['group_id']}.json"
    if source != old:
        source.rename(old)
    write_json(old, {**original, "group_id": identifier})
    before = old.read_bytes()
    second = send(client, shopper, "group")
    assert old.read_bytes() == before
    assert second.status_code == (200 if legacy else 409), second.text
    assert identifier in {g.group_id for g in interview.list_group_interviews(PID, RUN)}
