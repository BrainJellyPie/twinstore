"""Late product/starter draft lock acquisition must not recreate a deleted project."""

import pytest

from store_emulator.application.storage.setups import metadata_path
from tests.server.test_product_draft_source_races import draft, layout
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID


@pytest.mark.parametrize("phase", ["setup_path", "FileLock"])
def test_project_deletion_during_draft_preparation_leaves_no_orphan_directory(draft, monkeypatch, phase):
    client, url, body, module, _kind = draft
    root = metadata_path(PID).parent
    save, deleted = overlap(monkeypatch, module, phase,
                            lambda: client.post(url + "/save", json=body),
                            lambda: client.delete(f"/api/projects/{PID}"))
    assert deleted.status_code == 200, deleted.text
    assert save.status_code == 404, save.text
    assert not root.exists()
