"""A failed manifest write must not change the previously published photo."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage import images
from store_emulator.application.storage.io import write_json


def photo(color, fmt="PNG"):
    data = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(data, format=fmt)
    return data.getvalue()


@pytest.mark.parametrize("replacement_format", ["PNG", "JPEG"])
def test_failed_replacement_preserves_previous_photo(tmp_path, monkeypatch, replacement_format):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    from store_emulator.server.main import app
    client = TestClient(app, raise_server_exceptions=False)
    original = photo("red")
    uploaded = client.post("/api/projects/proj_test/sku-images", params={"sku": "tea"}, files={"file": ("tea.png", original, "image/png")})
    assert uploaded.status_code == 200, uploaded.text
    root = tmp_path / ".data" / "images" / "proj_test"
    before = {p.name: p.read_bytes() for p in root.iterdir()}

    def fail_manifest(*args):
        raise OSError("Simulated storage write failure")

    monkeypatch.setattr(images, "_save_manifest", fail_manifest)
    replacement = photo("blue", replacement_format)
    response = client.post("/api/projects/proj_test/sku-images", params={"sku": "tea"}, files={"file": ("replacement", replacement, "image/png")})
    assert response.status_code == 500, response.text
    assert client.get(uploaded.json()["url"]).content == original
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


def seed_photo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    images.save_image("proj_test", "tea", photo("red"), "tea.png")
    return tmp_path / ".data" / "images" / "proj_test"


@pytest.mark.parametrize("stage", ["backup", "image"])
def test_partial_write_failure_preserves_the_original_and_cleans_up(tmp_path, monkeypatch, stage):
    from pathlib import Path

    root = seed_photo(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    write_bytes = Path.write_bytes

    if stage == "backup":
        def fail_copy(source, destination, **kwargs):
            Path(destination).write_bytes(b"partial backup")
            raise OSError("Simulated backup failure")
        monkeypatch.setattr(images.shutil, "copyfile", fail_copy)
    else:
        def fail_write(path, data):
            if ".tmp-" in path.name:
                write_bytes(path, b"partial photo")
                raise OSError("Simulated image write failure")
            return write_bytes(path, data)
        monkeypatch.setattr(Path, "write_bytes", fail_write)

    with pytest.raises(OSError, match="Simulated"):
        images.save_image("proj_test", "tea", photo("blue"), "tea.png")
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


def test_failed_first_upload_does_not_leave_an_unpublished_photo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})

    def fail_manifest(*args):
        raise OSError("Simulated manifest failure")

    monkeypatch.setattr(images, "_save_manifest", fail_manifest)
    with pytest.raises(OSError, match="Simulated"):
        images.save_image("proj_test", "tea", photo("blue"), "tea.png")
    assert images.resolve_image("proj_test", "tea") is None
    assert list((tmp_path / ".data" / "images" / "proj_test").iterdir()) == []


def test_successful_replacement_removes_its_backup(tmp_path, monkeypatch):
    root = seed_photo(tmp_path, monkeypatch)
    blue = photo("blue")
    entry = images.save_image("proj_test", "tea", blue, "tea.png")
    resolved = images.resolve_image("proj_test", "tea")
    assert resolved is not None
    assert resolved[0].read_bytes() == blue
    assert images.load_manifest("proj_test")["tea"]["version"] == entry.version
    assert len(list(root.iterdir())) == 2
    assert not any(".backup-" in p.name or ".tmp-" in p.name for p in root.iterdir())


def test_failed_restore_keeps_the_original_backup_available(tmp_path, monkeypatch):
    from pathlib import Path

    root = seed_photo(tmp_path, monkeypatch)
    replace = Path.replace

    def fail_manifest(*args):
        raise OSError("Simulated manifest failure")

    def fail_restore(path, target):
        if ".backup-" in path.name:
            raise OSError("Simulated restore failure")
        return replace(path, target)

    monkeypatch.setattr(images, "_save_manifest", fail_manifest)
    monkeypatch.setattr(Path, "replace", fail_restore)
    with pytest.raises(OSError, match="restore failure"):
        images.save_image("proj_test", "tea", photo("blue"), "tea.png")
    backups = list(root.glob("*.backup-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == photo("red")
