"""Customer evidence cannot silently lose spreadsheet errors or uncached formulas."""

import json
from unittest.mock import Mock

import pytest

from store_emulator.application import generation_async, projects, supplemental
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.domain.config import SimulationConfig
from tests.engine.test_pos_array_formula_cells import array_workbook
from tests.engine.test_pos_formula_cells import workbook
from tests.server.test_project_templates import _meta, client
from tests.server.test_simulation_setup_races import PID, SID, layout


@pytest.mark.parametrize("data", [
    workbook("quantity", "=1+1"),
    workbook("quantity", "#REF!"),
    workbook("unit_price", "=1+1", cached=("e", "#SPILL!")),
    workbook("unit_price", "=1+1", cached=("n", "")),
    workbook("unit_price", '= "Amount"', header=True),
    workbook("unit_price", "=1+1", row=4),
    workbook("notes", "=1+1", sheet="second"),
    workbook("quantity", "=1+1", nonstandard=True),
    array_workbook("quantity", "missing"),
    array_workbook("quantity", "absent"),
    array_workbook("quantity", "saved", reference="C2:C4"),
], ids=["uncached", "error", "cached-error", "empty-numeric-cache", "header", "trailing-formula",
        "second-sheet", "custom-part", "array-empty", "array-absent", "array-tail"])
def test_unusable_workbook_is_rejected_before_models_or_project(client, monkeypatch, data):
    api, generation = client
    selection = Mock(side_effect=AssertionError("Invalid evidence cannot trigger product selection"))
    monkeypatch.setattr(projects, "select_initial_assortment", selection)
    before = api.get("/api/projects").json()
    response = api.post("/api/projects/create-store", data={"meta": json.dumps({**_meta(),
        "starter_selection": "automatic", "layout": {"template_id": "community_pharmacy"}})},
        files={"supplemental": ("customers.xlsx", data)})
    assert response.status_code == 400, response.text[:300]
    assert "formula" in response.text.lower() and "Excel workbook" in response.text
    generation.assert_not_called()
    selection.assert_not_called()
    assert api.get("/api/projects").json() == before
    assert supplemental._load_frames(data, ".xlsx") == {}


@pytest.mark.parametrize("cached", [("n", "0"), ("n", "125"), ("str", ""), ("str", "00123")])
def test_cached_formula_values_remain_usable(cached):
    frame = supplemental.read_customer_workbook(workbook("unit_price", "=1+1", cached=cached),
        preserve_identifiers=True)["Sheet"]
    expected = int(cached[1]) if cached[0] == "n" else cached[1]
    assert frame.iloc[0]["unit_price"] == expected


@pytest.mark.parametrize("child", ["saved", "zero", "empty_text"])
def test_cached_array_results_remain_usable(child):
    frame = supplemental.read_customer_workbook(array_workbook("unit_price", child), preserve_identifiers=True)["Sheet"]
    assert frame.shape[0] == 2
    assert frame.iloc[1]["unit_price"] == {"saved": 300, "zero": 0, "empty_text": ""}[child]


@pytest.mark.parametrize("summary", ["", "Previous automatic summary"])
@pytest.mark.parametrize("data", [workbook("quantity", "=1+1"), array_workbook("quantity", "absent")],
    ids=["ordinary", "array"])
def test_legacy_retained_formula_errors_block_retry_before_replacing_customers(layout, monkeypatch, data, summary):
    folder = generation_async._upload_dir(PID)
    write_json(folder / "upload.json", {"filename": "customers.xlsx"})
    (folder / "upload.xlsx").write_bytes(data)
    meta = read_json(metadata_path(PID))
    write_json(metadata_path(PID), {**meta, "supplemental_summary": summary})
    before = personas_path(PID).read_bytes()
    pool = Mock()
    monkeypatch.setattr(generation_async, "executor", pool)
    with pytest.raises(AppError) as error:
        generation_async.start_persona_generation(SimulationConfig(), PID, SID)
    assert error.value.status_code == 409
    pool.submit.assert_not_called()
    assert personas_path(PID).read_bytes() == before
    assert not list(metadata_path(PID).parent.glob("generations/*/status.json"))


@pytest.mark.parametrize("data", [workbook("unit_price", "=1+1", cached=("n", "0")),
    array_workbook("unit_price", "empty_text")], ids=["zero", "empty-array"])
def test_retained_cached_results_can_be_queued_again(layout, monkeypatch, data):
    generation_async._keep_upload(PID, data, "customers.XLSX")
    before = personas_path(PID).read_bytes()
    pool = Mock()
    monkeypatch.setattr(generation_async, "executor", pool)
    job = generation_async.start_persona_generation(SimulationConfig(), PID, SID)
    assert job
    pool.submit.assert_called_once()
    assert pool.submit.call_args.kwargs["supplemental_bytes"] == data
    assert pool.submit.call_args.kwargs["supplemental_filename"] == "customers.XLSX"
    assert personas_path(PID).read_bytes() == before
