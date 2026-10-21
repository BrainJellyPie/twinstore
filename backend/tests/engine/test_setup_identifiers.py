"""Distinct UUIDs must not collapse to one layout ID and overwrite a parent layout."""

from itertools import count
import json
import subprocess
import sys
from uuid import UUID

import pytest

from store_emulator.application import setups
from store_emulator.application.storage import io
from store_emulator.application.storage.setups import create_initial_setup, list_setups, read_setup, write_setup


def test_branching_preserves_parent_when_generated_uuids_share_a_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sequence = count(1)
    monkeypatch.setattr(io.uuid, "uuid4", lambda: UUID(int=(0xABCD << 112) + next(sequence)))

    root = create_initial_setup("proj_test")
    original = read_setup("proj_test", root["id"])
    branch = setups.create_setup_from_source("proj_test", root["id"], "empty", name="Branch")

    assert branch["id"] != root["id"]
    assert branch["parentId"] == root["id"]
    assert read_setup("proj_test", root["id"]) == original
    assert len(list_setups("proj_test")) == 2


@pytest.mark.parametrize("parents, expected", [
    ({"setup_a": "setup_a"}, []),
    ({"setup_a": "setup_c", "setup_b": "setup_a", "setup_c": "setup_b"}, ["setup_b", "setup_c"]),
])
def test_legacy_cyclic_layouts_do_not_hang_descendant_lookup(tmp_path, monkeypatch, parents, expected):
    monkeypatch.chdir(tmp_path)
    for sid, parent in parents.items():
        write_setup("proj_test", sid, {"id": sid, "parentId": parent})
    # A separate process bounds regressions that would otherwise loop forever.
    result = subprocess.run([
        sys.executable, "-c",
        "import json; from store_emulator.application.storage.setups import find_descendants; "
        "print(json.dumps(find_descendants('proj_test', 'setup_a')))",
    ], capture_output=True, text=True, timeout=3, check=True)
    assert json.loads(result.stdout) == expected
