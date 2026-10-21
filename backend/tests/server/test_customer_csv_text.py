"""Customer exports keep descriptive text literal and preserve numeric/missing cells."""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.types import Action, Weekday


TEXT_CASES = [
    ("=1+1", "'=1+1"), ("+1+1", "'+1+1"), ("-1+1", "'-1+1"),
    ("@SUM(1,2)", "'@SUM(1,2)"), (" \t=1+1", "' \t=1+1"),
    ("\r\n+1+1", "'\r\n+1+1"), ("-20% sugar", "'-20% sugar"),
    ("Regular", "Regular"), ('Tea, "large"', 'Tea, "large"'),
    ("Zero\nsugar", "Zero\nsugar"), ("'=1+1", "'=1+1"),
    ("茶·선물", "茶·선물"), ("0", "0"), ("", ""),
]


@pytest.mark.parametrize("text,expected", TEXT_CASES)
@pytest.mark.parametrize("field", ["persona_id", "identity", "age_group", "gender", "purpose", "products"])
def test_customer_csv_quotes_formula_text_without_modifying_saved_results(tmp_path, monkeypatch, field, text, expected):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    base = root / "runs" / "run_test"
    write_json(root / "metadata.json", {})
    pid = text if field == "persona_id" else "p_test"
    product = text if field == "products" else "Free tea"
    customer = CustomerResult(persona_id=pid, day=Weekday.MON, arrival_time="00:00:00", leave_time="00:00:05",
        timeline=[TimelineEvent(elapsed_sec=5, x=0, y=0, action=Action.BUY, product_sku="tea",
                                product_name=product, price=0, quantity=2, origin="impulse")])
    empty = CustomerResult(persona_id="p_missing", day=Weekday.TUE, arrival_time="12:00:00")
    persona = {"identity": "Visitor", "age_group": "20s", "gender": "Male", "purpose": "Browse",
               "arrival_hour": 0, "budget_min": 0, "budget_max": None}
    if field in persona:
        persona[field] = text
    write_json(base / "output" / "timeline.json", [customer.model_dump(mode="json"), empty.model_dump(mode="json")])
    write_json(base / "output" / "personas.json", {pid: persona})
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")}
    from store_emulator.server.main import app

    response = TestClient(app).get("/api/projects/proj_test/runs/run_test/export.csv")

    assert response.status_code == 200, response.text
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert rows[0][field] == (expected + " x2" if field == "products" else expected)
    assert [rows[0][key] for key in ["day", "arrival_hour", "budget_min", "budget_max", "spend", "units", "bought", "impulse_spend", "visit_sec", "path_tiles"]] == ["1", "0", "0", "", "0", "2", "1", "0", "5", "0"]
    assert rows[1]["products"] == "" and rows[1]["leave_time"] == ""
    assert all(rows[1][key] == "" for key in persona)
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")} == before
