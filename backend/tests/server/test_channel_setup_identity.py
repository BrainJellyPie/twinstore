"""Malformed optional layout metadata must not become a clickable fake layout ID."""

import json

import pytest

from store_emulator.application import channels


@pytest.mark.parametrize("setup", [None, 17, False, [], {}, "", "  ", "setup_existing"])
def test_finished_run_retains_only_a_nonempty_text_layout_id(tmp_path, monkeypatch, setup):
    monkeypatch.setattr(channels, "DATA_DIR", str(tmp_path))
    folder = tmp_path / "project" / "runs" / "finished"
    for path in ["output/timeline.json", "output/personas.json", "input/store.json"]:
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
    (folder / "status.json").write_text(json.dumps({"status": "completed", "created_at": "2026-10-25", "setup_id": setup}))
    expected = setup.strip() if isinstance(setup, str) else ""
    assert channels._store_runs("project") == [("finished", "2026-10-25", expected)]
