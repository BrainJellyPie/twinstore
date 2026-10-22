"""Failed atomic saves preserve the old JSON and remove incomplete temporary files."""
from pathlib import Path

import pytest

from store_emulator.application.storage import io as storage_io
from store_emulator.engine import files


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("stage", ["write", "replace", "serialize"])
def test_failed_atomic_save_preserves_old_data_without_leaving_partial_files(tmp_path, monkeypatch, existing, stage):
    path = tmp_path / "metadata.json"
    if existing:
        storage_io.write_json(path, {"saved": "original"})
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    data = {"saved": "replacement"}
    if stage == "write":
        def fail_write(value, stream, **kwargs):
            stream.write('{"partial":')
            raise OSError("Simulated disk write failure")
        monkeypatch.setattr(storage_io.json, "dump", fail_write)
    elif stage == "replace":
        def fail_replace(source, destination):
            raise OSError("Simulated replacement failure")
        monkeypatch.setattr(files.os, "replace", fail_replace)
    else:
        data["cycle"] = data
    with pytest.raises((OSError, ValueError)):
        storage_io.write_json(path, data)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_successful_atomic_save_publishes_json_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "metadata.json"
    storage_io.write_json(path, {"saved": "original"})
    storage_io.write_json(path, {"saved": "replacement"})
    assert storage_io.read_json(path) == {"saved": "replacement"}
    assert list(tmp_path.iterdir()) == [path]


def test_cleanup_failure_does_not_hide_the_original_storage_error(tmp_path, monkeypatch, caplog):
    path = tmp_path / "metadata.json"
    storage_io.write_json(path, {"saved": "original"})
    original = path.read_bytes()
    unlink = Path.unlink

    def fail_write(value, stream, **kwargs):
        stream.write('{"partial":')
        raise OSError("Original write error")

    def fail_cleanup(target, *args, **kwargs):
        if ".tmp-" in target.name:
            raise PermissionError("Cleanup error")
        return unlink(target, *args, **kwargs)

    monkeypatch.setattr(storage_io.json, "dump", fail_write)
    monkeypatch.setattr(Path, "unlink", fail_cleanup)
    with pytest.raises(OSError, match="Original write error"):
        storage_io.write_json(path, {"saved": "replacement"})
    assert path.read_bytes() == original
    assert "Could not remove temporary JSON file" in caplog.text
