"""Files an earlier version left empty, NUL-filled or cut short (before 0.4.3 a save was not flushed to disk before it
replaced the old file, so a power cut or forced shutdown could leave it so): lists show everything else, the store
still opens, and a damaged object says which file it is instead of "Internal Server Error"."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_b1fe9f16"
OTHER = "proj_67916afd"
SETUP = "setup_6cebe388c144493c82d69b2b34788337"
BROKEN_SETUP = "setup_01cc57e15b9e4e8c859af232efbedc7f"

# As 0.4.0 wrote them (trimmed: one weekday, one shelf with one product).
METADATA = {"project_id": PID, "name": "Old v0.4.0 store", "description": "made by old version", "store_type": "convenience",
            "grid_size": [12, 10], "weekly_schedule": [{"day": 1, "is_open": True, "open_hour": 9, "close_hour": 21}],
            "address": "Seoul", "customer_profile": "office workers", "supplemental_summary": "",
            "created_at": "2026-10-22T16:20:32.672489+00:00", "updated_at": "2026-10-22T16:20:34.710212+00:00",
            "currency": "KRW"}
PERSONAS = [{"id": "M1001", "day": 1, "identity": "Corporate executives", "age_group": "50s", "gender": "Male",
             "description": "A senior director arriving early.", "intent": "Wants a black coffee.",
             "purpose": "Monday morning breakfast", "arrival_hour": 10, "preferred_categories": ["Coffee", "Bakery"],
             "budget_min": 500, "budget_max": 1500, "behavior_tendency": "Moves purposefully.", "basket_size": 0,
             "basket_kinds": 0, "category_rates": {}, "usual_products": []}]
RACK = {"rotation": 0, "levels": 4, "dwell_min": 2, "dwell_max": 30, "rack_desc": "", "rack_decoration_desc": "",
        "design_variant": "a", "locked_faces": []}
STORE = {"id": f"store_{PID}", "name": "Edited by old", "type": "convenience", "design_theme": "classic",
         "design_colors": None, "currency": "KRW", "grid_size": [12, 10],
         "weekly_schedule": [{"day": 1, "is_open": True, "open_hour": 9, "close_hour": 21}],
         "racks": [
             {**RACK, "id": "r_000", "type": "entrance", "shape": [[1]], "position": [0, 9], "rack_name": "", "slots": []},
             {**RACK, "id": "r_exit", "type": "exit", "shape": [[1]], "position": [0, 9], "rack_name": "", "slots": []},
             {**RACK, "id": "r_002", "type": "counter", "shape": [[1]], "position": [2, 9], "rack_name": "Counter 1", "slots": []},
             {**RACK, "id": "r_003", "type": "shelf", "shape": [[1]], "position": [1, 9], "rack_name": "Snacks 1",
              "slots": [{"block": 0, "face": "N", "level": 3, "items": [
                  {"sku": "g_a256563c436f98ee11c6503c7a55e23e", "name": "Mints", "price": 1300, "regular_price": 0,
                   "promo": "", "image_url": None}]}]},
         ]}
SETUP_FILE = {"id": SETUP, "name": "clone B", "status": "draft", "parentId": None, "store": STORE, "runId": None,
              "memo": "", "created_at": "2026-10-22T16:20:34.797148+00:00", "updated_at": "2026-10-22T16:20:36.408061+00:00"}
RUN_STATUS = {"status": "completed", "error": "", "setup_id": SETUP, "preview": True,
              "created_at": "2026-10-22T16:20:35.894393+00:00", "total_customers": 0, "completed_customers": 0,
              "failed_customers": 0, "engine_type": "rule_based", "seed": 1, "replicate": 0,
              "started_at": "2026-10-22T16:20:35.898235+00:00", "scenario": "", "finished_at": "2026-10-22T16:20:36.403903+00:00"}
GENERATION = {"created_at": "2026-10-22T16:20:32.692647+00:00", "status": "failed", "updated_at": "2026-10-22T16:20:33.806189+00:00",
              "kind": "persona", "setup_id": SETUP, "error": "API key not valid."}
CAPTURE = {"capture_id": "cap_6b5d4e36", "status": "completed", "stage": "done", "progress": 1.0, "error": "",
           "options": {"detector": "classic", "model": "", "currency": "KRW", "rack_type": "shelf", "label": "old shelf"},
           "image_name": "shelf.png", "image_size": [640, 480], "created_at": "2026-10-22T16:29:51.200372+00:00",
           "finished_at": "2026-10-22T16:29:53.485056+00:00", "items": 1, "facings": 1, "gaps": 0, "levels": 1,
           "applied_setup_ids": [], "upload_sha256": ""}
EXPERIMENT = {"job_id": "exp_81db78678ef6", "kind": "experiment", "name": "old discount test", "status": "failed",
              "stage": "control", "progress": 0.0, "error": "ValueError: Control produced no successful shopper results.",
              "created_at": "2026-10-22T16:30:00.989573+00:00", "finished_at": "2026-10-22T16:30:01.624517+00:00"}
OPTIMIZATION = {"job_id": "opt_ee0a20", "setup_id": SETUP, "status": "completed", "phase": "done",
                "judge": {"judge": "rule", "model": None, "ensemble": None, "vlm_customers": 60, "top_k": 4, "calibrate": True},
                "error": "", "evaluations": 3, "budget": 3, "baseline_score": 0.0, "best_score": 0.0, "scenario": "",
                "spec": {"objective": "revenue_per_visitor", "scope": "planogram", "algorithm": "hill_climb", "budget": 3,
                         "eval_customers": 10, "validation_customers": None, "seed": 1,
                         "constraints": {"keep_fridges_on_walls": True, "lock_rack_ids": [], "max_moves": 10,
                                         "min_improvement": 0.0}},
                "created_at": "2026-10-22T16:20:41.801103+00:00", "finished_at": "2026-10-22T16:20:43.766439+00:00",
                "applied_setup_id": None}

DAMAGE = {"empty": b"", "zeroed": b"\0" * 300, "cut": b'{\n  "status": "comp'}


def _write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _old_data(root: Path, damage: bytes) -> Path:
    """Two stores as 0.4.0 left them; in the first, one of each kind of file is damaged."""
    data = root / ".data"
    for pid in (PID, OTHER):
        project = data / pid
        _write(project / "metadata.json", {**METADATA, "project_id": pid, "name": f"store {pid}"})
        _write(project / "personas.json", PERSONAS)
        _write(project / "state.json", {"activeSetupId": SETUP})
        _write(project / "setups" / f"{SETUP}.json", SETUP_FILE)
    project = data / PID
    (project / "state.json").write_bytes(damage)
    (project / "personas.json").write_bytes(damage)
    (project / "setups" / f"{BROKEN_SETUP}.json").write_bytes(damage)
    _write(project / "runs" / "run_629205" / "status.json", RUN_STATUS)
    _write(project / "runs" / "run_629205" / "output" / "summary.json", {"currency": "KRW", "total_customers": 0})
    (project / "runs" / "run_4ee863").mkdir(parents=True)
    (project / "runs" / "run_4ee863" / "status.json").write_bytes(damage)
    _write(project / "runs" / "run_aa0001" / "status.json", {**RUN_STATUS, "created_at": "2026-10-22T17:00:00+00:00"})
    (project / "runs" / "run_aa0001" / "output").mkdir(parents=True)
    (project / "runs" / "run_aa0001" / "output" / "summary.json").write_bytes(damage)
    _write(project / "generations" / "gen_c48959438d" / "status.json", GENERATION)
    (project / "generations" / "gen_d00000000a").mkdir(parents=True)
    (project / "generations" / "gen_d00000000a" / "status.json").write_bytes(damage)
    _write(project / "captures" / "cap_6b5d4e36" / "status.json", CAPTURE)
    (project / "captures" / "cap_d0000000").mkdir(parents=True)
    (project / "captures" / "cap_d0000000" / "status.json").write_bytes(damage)
    _write(project / "marketing" / "experiments" / "exp_81db78678ef6" / "status.json", EXPERIMENT)
    (project / "marketing" / "experiments" / "exp_d00000000000").mkdir(parents=True)
    (project / "marketing" / "experiments" / "exp_d00000000000" / "status.json").write_bytes(damage)
    _write(project / "optimizations" / "opt_ee0a20" / "status.json", OPTIMIZATION)
    (project / "optimizations" / "opt_d00000").mkdir(parents=True)
    (project / "optimizations" / "opt_d00000" / "status.json").write_bytes(damage)
    return data


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM", "0")
    from store_emulator.server import main
    monkeypatch.setattr(main, "seed_sample_projects", lambda: 0)
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE.keys())
def test_lists_and_the_store_page_survive_damaged_files(tmp_path: Path, client: TestClient, damage: bytes):
    data = _old_data(tmp_path, damage)
    before = {p: p.read_bytes() for p in data.rglob("*") if p.is_file()}

    projects = client.get("/api/projects")
    assert projects.status_code == 200, projects.text
    listed = {p["project_id"]: p for p in projects.json()}
    assert set(listed) == {PID, OTHER}
    assert listed[PID]["status"] == "Setting up"     # its customers cannot be read
    assert listed[OTHER]["status"] == "Ready"

    page = client.get(f"/api/projects/{PID}")
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["personas"] == [] and body["state"] == {"activeSetupId": None}
    assert [s["id"] for s in body["setups"]] == [SETUP]
    assert body["setups"][0]["readiness"]["reasons"] == ["no_personas"]

    setups = client.get(f"/api/projects/{PID}/setups")
    assert setups.status_code == 200 and [s["id"] for s in setups.json()] == [SETUP]
    assert client.get(f"/api/projects/{PID}/setups/{SETUP}").status_code == 200
    gens = client.get(f"/api/projects/{PID}/setups/{SETUP}/generations")
    assert gens.status_code == 200 and [g["gen_id"] for g in gens.json()] == ["gen_c48959438d"]

    runs = client.get(f"/api/projects/{PID}/runs")
    assert runs.status_code == 200, runs.text
    by_id = {r["run_id"]: r for r in runs.json()}
    assert by_id["run_629205"]["status"] == "completed" and by_id["run_629205"]["summary"]["currency"] == "KRW"
    assert by_id["run_4ee863"]["status"] == "failed"
    assert "runs/run_4ee863/status.json is damaged" in by_id["run_4ee863"]["error"]
    assert by_id["run_aa0001"]["status"] == "completed" and "summary" not in by_id["run_aa0001"]
    assert [r["run_id"] for r in client.get(f"/api/projects/{PID}/runs", params={"setup_id": SETUP}).json()] == [
        "run_aa0001", "run_629205"]

    assert [c["capture_id"] for c in client.get(f"/api/projects/{PID}/captures").json()] == ["cap_6b5d4e36"]
    assert [e["job_id"] for e in client.get(f"/api/projects/{PID}/experiments").json()] == ["exp_81db78678ef6"]
    assert [o["job_id"] for o in client.get(f"/api/projects/{PID}/optimizations").json()] == ["opt_ee0a20"]

    # Nothing was rewritten: the damaged files stay as they are for the user to recover or delete.
    assert {p: p.read_bytes() for p in data.rglob("*") if p.is_file() and p.parent.name != "locks"} == {
        p: b for p, b in before.items()}


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE.keys())
def test_a_store_whose_settings_file_is_damaged_is_still_listed(tmp_path: Path, client: TestClient, damage: bytes):
    data = _old_data(tmp_path, damage)
    (data / OTHER / "metadata.json").write_bytes(damage)
    listed = {p["project_id"]: p for p in client.get("/api/projects").json()}
    assert set(listed) == {PID, OTHER}
    assert listed[OTHER]["name"] == "Edited by old"                  # its open layout's store
    assert "metadata.json) is damaged" in listed[OTHER]["description"]
    assert listed[OTHER]["status"] == "Ready" and listed[OTHER]["footprint"]["grid"] == [12, 10]
    opened = client.get(f"/api/projects/{OTHER}")
    assert opened.status_code == 500 and f"{OTHER}/metadata.json is damaged" in opened.json()["detail"]
    assert (data / OTHER / "metadata.json").read_bytes() == damage


@pytest.mark.parametrize("damage", DAMAGE.values(), ids=DAMAGE.keys())
@pytest.mark.parametrize(("path", "file"), [
    ("runs/run_4ee863/status", "runs/run_4ee863/status.json"),
    ("runs/run_aa0001/summary", "runs/run_aa0001/output/summary.json"),
    (f"setups/{BROKEN_SETUP}", f"setups/{BROKEN_SETUP}.json"),
    (f"setups/{SETUP}/generations/gen_d00000000a/status", "generations/gen_d00000000a/status.json"),
    ("captures/cap_d0000000", "captures/cap_d0000000/status.json"),
    ("experiments/exp_d00000000000", "marketing/experiments/exp_d00000000000/status.json"),
])
def test_a_damaged_object_names_its_file(tmp_path: Path, client: TestClient, damage: bytes, path: str, file: str):
    _old_data(tmp_path, damage)
    response = client.get(f"/api/projects/{PID}/{path}")
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert f"{PID}/{file} is damaged and cannot be read" in detail


def test_read_json_reports_the_kind_of_damage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from store_emulator.application.storage.io import DamagedFile, read_json

    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".data" / PID / "state.json"
    path.parent.mkdir(parents=True)
    for content, reason in ((b"", "empty"), (b"\0\0\0", "empty"), (b'{"activeSetupId": "set', "cut off"),
                            (b"\xff\xfe", "not text")):
        path.write_bytes(content)
        with pytest.raises(DamagedFile, match=reason) as caught:
            read_json(path)
        assert isinstance(caught.value, ValueError) and caught.value.path == path
