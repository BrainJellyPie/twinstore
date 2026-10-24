"""Independent shelf studies and edited photographs cannot replace saved history."""

from types import SimpleNamespace
from uuid import UUID

import pytest

from store_emulator.application import shelf_lab
from store_emulator.application.storage.io import read_json, write_json
from tests.server.test_shelf_lab_start_snapshot import CID, lab  # noqa: F401
from tests.server.test_simulation_setup_races import PID, layout  # noqa: F401


@pytest.fixture(autouse=True)
def product_box(lab):
    root = lab[3]
    result = read_json(root / "result.json")
    result["items"][0]["boxes"] = [{"x1": 30, "y1": 20, "x2": 110, "y2": 100}]
    write_json(root / "result.json", result)


def begin(client, kind, body, price=200):
    base = f"/api/projects/{PID}/captures/{CID}"
    return client.post(base + ("/edits" if kind == "edit" else f"/{kind}"),
        json={"edits": [{"kind": "price", "item_id": "i1", "price": price}]} if kind == "edit"
        else body if kind == "audit" else {})


def destination(root, kind, identifier):
    return root / "lab" / ("edits" if kind == "edit" else "jobs") / identifier


@pytest.mark.parametrize("kind", ["edit", "audit", "sim2real"])
def test_distinct_uuids_with_the_same_prefix_preserve_the_first_result(lab, monkeypatch, kind):
    client, _, body, root = lab
    ids = iter([UUID("abcdef00-0000-4000-8000-000000000001"), UUID("abcdef00-0000-4000-8000-000000000002")])
    monkeypatch.setattr(shelf_lab, "uuid", SimpleNamespace(uuid4=lambda: next(ids)))
    first = begin(client, kind, body)
    assert first.status_code == 200, first.text
    key = "edit_id" if kind == "edit" else "job_id"
    old = destination(root, kind, first.json()[key])
    before = {p.name: p.read_bytes() for p in old.iterdir()}

    second = begin(client, kind, body, price=500)
    assert second.status_code == 200, second.text
    assert {p.name: p.read_bytes() for p in old.iterdir()} == before
    assert second.json()[key] != first.json()[key]
    assert len(list(old.parent.iterdir())) == 2


@pytest.mark.parametrize("kind", ["edit", "audit", "sim2real"])
def test_reusing_a_full_identifier_cannot_overwrite_an_existing_folder(lab, monkeypatch, kind):
    client, submit, body, root = lab
    identifier = UUID("abcdef00-0000-4000-8000-000000000001")
    monkeypatch.setattr(shelf_lab, "uuid", SimpleNamespace(uuid4=lambda: identifier))
    prefix = {"edit": "edit", "audit": "aud", "sim2real": "s2r"}[kind]
    old = destination(root, kind, f"{prefix}_{identifier.hex}")
    write_json(old / "retained.json", {"saved": "preserve all previous outputs"})
    before = {p.name: p.read_bytes() for p in old.iterdir()}

    response = begin(client, kind, body)
    assert response.status_code == 409, response.text
    assert {p.name: p.read_bytes() for p in old.iterdir()} == before
    assert len(list(old.parent.iterdir())) == 1
    submit.assert_not_called()


@pytest.mark.parametrize("kind", ["edit", "audit", "sim2real"])
def test_old_short_identifiers_remain_readable(lab, kind):
    client, _, body, root = lab
    response = begin(client, kind, body)
    assert response.status_code == 200, response.text
    key = "edit_id" if kind == "edit" else "job_id"
    original = response.json()
    prefix = {"edit": "edit", "audit": "aud", "sim2real": "s2r"}[kind]
    legacy_id = f"{prefix}_123abc"
    legacy = destination(root, kind, legacy_id)
    destination(root, kind, original[key]).rename(legacy)
    write_json(legacy / ("edit.json" if kind == "edit" else "status.json"), {**original, key: legacy_id})
    if kind == "edit":
        assert shelf_lab.get_edit(PID, CID, legacy_id).edit_id == legacy_id
    else:
        assert shelf_lab.get_job(PID, CID, legacy_id).status.job_id == legacy_id
