"""Creating a store must never reset another project's customers or metadata."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID

import pytest

from store_emulator.application import projects
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from tests.server.test_project_templates import _meta, client  # noqa: F401

IDENTIFIER = UUID("abcdef01-0000-4000-8000-000000000001")


def create(api, template, name):
    meta = {**_meta(), "name": name, "starter_selection": "format"}
    if template:
        meta["layout"] = {"template_id": "station_kiosk", "currency": "USD"}
    return api.post("/api/projects/create-store", data={"meta": json.dumps(meta)})


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


@pytest.mark.parametrize("template", [False, True])
def test_distinct_uuids_sharing_eight_digits_preserve_existing_customers_and_history(client, monkeypatch, template):
    api, generation = client
    ids = iter([IDENTIFIER, UUID(int=IDENTIFIER.int + 1)])
    monkeypatch.setattr(projects, "uuid", SimpleNamespace(uuid4=lambda: next(ids)))
    first = create(api, template, "Original store")
    assert first.status_code == 200, first.text
    pid = first.json()["metadata"]["project_id"]
    old = metadata_path(pid).parent
    write_json(personas_path(pid), [{"retained_customer": "Do not reset this population"}])
    write_json(old / "runs" / "run_saved" / "status.json", {"status": "completed", "retain": True})
    before = snapshot(old)
    second = create(api, template, "Different store")
    assert second.status_code == 200, second.text
    assert snapshot(old) == before
    assert second.json()["metadata"]["project_id"] != pid
    assert generation.call_count == 2


@pytest.mark.parametrize("template", [False, True])
@pytest.mark.parametrize("occupied", ["full", "legacy", "empty", "file"])
def test_occupied_project_destination_is_never_reused(client, monkeypatch, template, occupied):
    api, generation = client
    monkeypatch.setattr(projects, "uuid", SimpleNamespace(uuid4=lambda: IDENTIFIER))
    pid = "proj_abcdef01" if occupied == "legacy" else f"proj_{IDENTIFIER.hex}"
    old = metadata_path(pid).parent
    if occupied == "file":
        old.write_bytes(b"Retained file at an occupied project path")
    else:
        old.mkdir(parents=True)
        if occupied != "empty":
            write_json(metadata_path(pid), {"project_id": pid, "name": "Existing store"})
            write_json(personas_path(pid), [{"retained_customer": True}])
    before = old.read_bytes() if occupied == "file" else snapshot(old)
    response = create(api, template, "New store")
    assert (old.read_bytes() if occupied == "file" else snapshot(old)) == before
    assert response.status_code == (200 if occupied == "legacy" else 409), response.text
    assert generation.call_count == int(occupied == "legacy")


@pytest.mark.parametrize("template", [False, True])
def test_concurrent_creation_with_the_same_identifier_has_one_owner(client, monkeypatch, template):
    api, generation = client
    ready = Barrier(2)

    def identifier():
        ready.wait(timeout=5)
        return IDENTIFIER

    monkeypatch.setattr(projects, "uuid", SimpleNamespace(uuid4=identifier))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda name: create(api, template, name), ["First store", "Second store"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    saved = next(response.json() for response in responses if response.status_code == 200)
    project = api.get(f"/api/projects/{saved['metadata']['project_id']}")
    assert project.status_code == 200, project.text
    assert project.json()["metadata"]["name"] == saved["metadata"]["name"]
    generation.assert_called_once()
