"""Late model commentary must not recreate deleted studies or projects."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing, staff_pitch, study_reading
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.marketing import JobStatus
from store_emulator.engine.marketing.reading import StudyReading
from store_emulator.engine.marketing.report import ReportNarrative
from store_emulator.server.main import app

PID, JID = "proj_commentary", "study_saved"
KINDS = ["experiment", "survey", "shelf", "conjoint", "pitch"]
ROUTES = {"experiment": "experiments", "survey": "surveys", "shelf": "shelf-tests",
          "conjoint": "conjoints", "pitch": "staff-pitches"}


@pytest.fixture(params=KINDS)
def study(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kind = request.param
    write_json(metadata_path(PID), {"id": PID, "name": "Commentary"})
    folder = marketing._job_dir(PID, kind, JID)
    write_json(folder / "status.json", JobStatus(job_id=JID, kind=kind, status="completed").model_dump(mode="json"))
    report = {
        "experiment_id": JID, "survey_id": JID, "test_id": JID, "conjoint_id": JID, "pitch_id": JID,
        "name": "Saved result", "setup_id": "setup_original", "engine": "rule", "model": "offline",
        "panel_size": 20, "currency": "USD", "visitors_per_day": 20,
        "control": {"name": "Control"}, "variants": [], "stimuli": ["Tea"], "stimulus_names": ["Tea"],
        "questions": ["open"], "respondents": 20, "errors": 0, "rack_id": "rack", "rack_name": "Tea",
        "face": "N", "target_sku": "tea", "target_name": "Tea", "attributes": [], "options": 2,
        "none_option": True, "product": "Tea", "attempted": 20, "pairs": 20, "excluded": 0,
        "comparisons": [], "segments": [], "screening_leader": None, "recommendation": "Keep testing",
        "answers": [], "notes": [],
    }
    if kind == "pitch":
        report["product"] = {"sku": "tea", "name": "Tea", "price": 100, "currency": "USD"}
        report["request"] = {"setup_id": "setup_original", "sku": "tea", "context": "At the shelf",
                             "variants": [{"name": "A", "script": "Try this tea"},
                                          {"name": "B", "script": "Tea is on offer"}]}
    write_json(folder / "report.json", report)
    for module in (marketing, study_reading):
        monkeypatch.setattr(module, "assistive_model", lambda *args: "offline")
        monkeypatch.setattr(module, "assistive_client", lambda *args: object())
        monkeypatch.setattr(module, "answered_by", lambda *args: "offline")
    url = f"/api/projects/{PID}/{ROUTES[kind]}/{JID}"
    return TestClient(app, raise_server_exceptions=False), kind, folder, url


@pytest.mark.parametrize("parent", ["study", "project"])
@pytest.mark.parametrize("phase", ["input", "provider", "commit"])
def test_commentary_coordinates_input_and_commit_but_allows_deletion_during_provider(
    study, monkeypatch, parent, phase,
):
    client, kind, folder, url = study
    entered, release = Event(), Event()
    target = "narrative.json" if kind == "experiment" else "reading.json"
    suffix = "narrative" if kind == "experiment" else "reading"

    def pause():
        entered.set()
        assert release.wait(5), "commentary was not released"

    async def narrative(*args):
        if phase == "provider":
            pause()
        return ReportNarrative(summary="Saved result", interpretation="Observed differences", next_steps="Test again")

    async def reading(*args):
        if phase == "provider":
            pause()
        return StudyReading(summary="Saved result")

    monkeypatch.setattr(marketing, "write_narrative", narrative)
    monkeypatch.setattr(study_reading, "read_study", reading)
    if phase == "input":
        module = staff_pitch if kind == "pitch" else marketing
        original = module.read_json

        def read(path):
            if path == folder / "report.json":
                pause()
            return original(path)

        monkeypatch.setattr(module, "read_json", read)
    elif phase == "commit":
        module = marketing if kind == "experiment" else study_reading
        original = module.write_json

        def write(path, payload):
            if path == folder / target:
                pause()
            return original(path, payload)

        monkeypatch.setattr(module, "write_json", write)

    with ThreadPoolExecutor(max_workers=2) as pool:
        generating = pool.submit(client.post, f"{url}/{suffix}", json={})
        try:
            assert entered.wait(5), generating.result(timeout=0).text
            deletion = pool.submit(client.delete, url if parent == "study" else f"/api/projects/{PID}")
            if phase == "provider":
                deleted = deletion.result(timeout=2)
            else:
                with pytest.raises(TimeoutError):
                    deletion.result(timeout=.1)
        finally:
            release.set()
        response = generating.result(timeout=5)
        deleted = deletion.result(timeout=5)
    assert deleted.status_code == (204 if parent == "study" else 200), deleted.text
    # After the input snapshot, deletion may win the next lock before the final commit.
    expected = {404} if phase == "provider" else {200, 404} if phase == "input" else {200}
    assert response.status_code in expected, response.text
    assert not folder.exists()
    if parent == "project":
        assert not metadata_path(PID).parent.exists()
