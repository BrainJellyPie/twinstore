"""Sample projects are given to a data folder once; a sample the user deleted does not come back on restart."""

import json
from pathlib import Path

import pytest

from store_emulator.application.storage import seed


def _sample(root: Path, pid: str) -> None:
    (root / pid).mkdir(parents=True)
    (root / pid / "metadata.json").write_text(json.dumps({"project_id": pid, "name": "Sample"}), encoding="utf-8")


@pytest.fixture
def samples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "sample_data"
    _sample(root, "proj_sample1")
    monkeypatch.setattr(seed, "_SAMPLE_DATA_DIR", root)
    return root


def test_deleted_sample_is_not_seeded_again(samples: Path, tmp_path: Path) -> None:
    assert seed.seed_sample_projects() == 1
    assert (tmp_path / ".data" / "proj_sample1" / "metadata.json").is_file()

    (tmp_path / ".data" / "proj_sample1" / "metadata.json").unlink()
    (tmp_path / ".data" / "proj_sample1").rmdir()   # the user deleted the sample store
    assert seed.seed_sample_projects() == 0
    assert not (tmp_path / ".data" / "proj_sample1").exists()


def test_new_sample_of_an_update_is_still_seeded(samples: Path, tmp_path: Path) -> None:
    assert seed.seed_sample_projects() == 1
    _sample(samples, "proj_sample2")
    assert seed.seed_sample_projects() == 1
    assert (tmp_path / ".data" / "proj_sample2").is_dir()


def test_edited_sample_is_never_overwritten(samples: Path, tmp_path: Path) -> None:
    seed.seed_sample_projects()
    meta = tmp_path / ".data" / "proj_sample1" / "metadata.json"
    meta.write_text(json.dumps({"project_id": "proj_sample1", "name": "Mine now"}), encoding="utf-8")
    assert seed.seed_sample_projects() == 0
    assert json.loads(meta.read_text(encoding="utf-8"))["name"] == "Mine now"


def test_folder_seeded_by_an_earlier_version_keeps_a_deleted_sample_deleted(samples: Path, tmp_path: Path) -> None:
    # An earlier version kept no record; this folder has the user's own store and no sample (deleted there).
    _sample(tmp_path / ".data", "proj_mine")
    assert seed.seed_sample_projects() == 0
    assert not (tmp_path / ".data" / "proj_sample1").exists()
    assert json.loads((tmp_path / ".data" / "sample_projects.json").read_text(encoding="utf-8")) == {
        "offered": ["proj_sample1"]}


def test_unreadable_record_does_not_bring_samples_back(samples: Path, tmp_path: Path) -> None:
    (tmp_path / ".data").mkdir()
    (tmp_path / ".data" / "sample_projects.json").write_text("{", encoding="utf-8")
    _sample(tmp_path / ".data", "proj_mine")
    assert seed.seed_sample_projects() == 0
    assert not (tmp_path / ".data" / "proj_sample1").exists()
