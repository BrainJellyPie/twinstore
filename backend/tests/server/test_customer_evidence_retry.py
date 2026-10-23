"""A saved text summary does not prove the uploaded visit-time evidence was committed."""

import io
from unittest.mock import Mock

import pytest
from openpyxl import Workbook

from store_emulator.application import generation_async as generation
from store_emulator.application.storage.generations import read_status
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.persona import Persona
from store_emulator.domain.store import DaySchedule
from tests.server.test_simulation_setup_races import PID, SID, layout


def visits(kind):
    rows = [["receipt_id", "timestamp", "고객"], *[
        [f"{i:03d}", f"2026-10-19 {9 if i % 3 == 0 else 17:02d}:00:00", "방문"] for i in range(300)
    ]]
    if kind == "xlsx":
        book = Workbook()
        for row in rows:
            book.active.append(row)
        data = io.BytesIO()
        book.save(data)
        return data.getvalue(), "방문 기록.XLSX"
    text = "\n".join(",".join(row) for row in rows)
    return text.encode(kind), "방문 기록.CSV"


@pytest.mark.parametrize("kind", ["utf-8-sig", "cp949", "xlsx"])
@pytest.mark.parametrize("stored_summary", [False, True])
def test_retry_keeps_traffic_after_failure_between_summary_and_profile(layout, monkeypatch, kind, stored_summary):
    data, name = visits(kind)
    original_traffic = generation.traffic_from_supplemental
    expected = original_traffic(data, name)
    assert expected is not None and expected.weights[1][17] > expected.weights[1][9]
    meta = read_json(metadata_path(PID))
    meta.update(weekly_schedule=[DaySchedule(day=1, open_hour=8, close_hour=22).model_dump(mode="json")],
                supplemental_summary="Uploaded evidence" if stored_summary else "")
    write_json(metadata_path(PID), meta)
    previous = personas_path(PID).read_bytes()
    summary_calls = []
    traffic_calls = []
    generated = []

    async def summarize(*args):
        summary_calls.append(args)
        return "Uploaded evidence"

    def traffic(*args):
        traffic_calls.append(args)
        if len(traffic_calls) == 1:
            raise RuntimeError("Interrupted after saving text summary")
        return original_traffic(*args)

    async def customers(**kwargs):
        generated.append(kwargs)
        return [Persona.model_validate(read_json(personas_path(PID))[0])]

    monkeypatch.setattr(generation, "assistive_client", lambda *a, **k: Mock(max_parallel=None))
    monkeypatch.setattr(generation, "summarize_supplemental", summarize)
    monkeypatch.setattr(generation, "traffic_from_supplemental", traffic)
    monkeypatch.setattr(generation, "neighborhood_text", lambda *a: "")
    monkeypatch.setattr(generation, "_generate_personas_impl", customers)
    monkeypatch.setattr(generation.executor, "submit", lambda fn, *a, **k: fn(*a, **k))
    first = generation.start_persona_generation(SimulationConfig(), PID, SID,
        supplemental_bytes=data, supplemental_filename=name)
    assert read_status(PID, first)["status"] == "failed"
    assert read_json(metadata_path(PID))["supplemental_summary"] == "Uploaded evidence"
    assert personas_path(PID).read_bytes() == previous
    assert not generated

    second = generation.start_persona_generation(SimulationConfig(), PID, SID)
    assert read_status(PID, second)["status"] == "completed"
    assert generated[0]["traffic"] == expected
    assert generated[0]["supplemental_summary"] == "Uploaded evidence"
    assert read_json(metadata_path(PID))["traffic_profile"] == expected.model_dump(mode="json")
    assert len(summary_calls) == (0 if stored_summary else 1)

    # Another retry reuses the same text without paying to summarize it again.
    third = generation.start_persona_generation(SimulationConfig(), PID, SID)
    assert read_status(PID, third)["status"] == "completed"
    assert generated[1]["traffic"] == expected
    assert len(summary_calls) == (0 if stored_summary else 1)
