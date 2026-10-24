"""Uploading another photograph cannot replace previously saved image evidence."""

import io
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
from PIL import Image

from store_emulator.application import capture, projects, shelf_lab
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.capture import CaptureOptions, CaptureResult
from store_emulator.domain.config import SimulationConfig
from tests.server.test_shelf_lab_start_snapshot import overlap

PID = "image_identifiers"
IDENTIFIER = UUID("abcdef01-0000-4000-8000-000000000001")


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(metadata_path(PID), {"name": "Image evidence", "currency": "USD"})
    monkeypatch.setattr(capture.executor, "submit", Mock())


def save(kind, color="blue"):
    with Image.new("RGB", (160, 160), color) as photo:
        data = io.BytesIO()
        photo.save(data, format="PNG")
        options = CaptureOptions(detector="classic", model="none", currency="USD")
        if kind == "package":
            return shelf_lab.upload_package(PID, data.getvalue(), color + ".png", name=color,
                                             remove_background=False).asset_id
        if kind == "upload":
            return capture.create_capture(PID, data.getvalue(), color + ".png", options, SimulationConfig()).capture_id
        result = CaptureResult(image_size=photo.size, currency="USD", notes=[color])
        return capture.save_capture(PID, photo, color + ".png", options, result).capture_id


def files(kind, identifier):
    root = metadata_path(PID).parent
    if kind == "package":
        return {p.name: p.read_bytes() for p in (root / "lab_assets").glob(identifier + ".*")}
    folder = root / "captures" / identifier
    return {p.name: p.read_bytes() for p in folder.iterdir()}


@pytest.mark.parametrize("kind", ["package", "upload", "computed"])
def test_matching_uuid_prefixes_keep_both_photographs_and_metadata(monkeypatch, kind):
    ids = iter([IDENTIFIER, UUID(int=IDENTIFIER.int + 1)])
    module = shelf_lab if kind == "package" else capture
    monkeypatch.setattr(module, "uuid", SimpleNamespace(uuid4=lambda: next(ids)))
    first = save(kind)
    before = files(kind, first)
    second = save(kind, "red")
    assert files(kind, first) == before
    assert second != first
    assert files(kind, second) != before


@pytest.mark.parametrize("kind, occupied", [("package", "image"), ("package", "metadata"),
                                           ("package", "both"), ("upload", "folder"), ("computed", "folder")])
def test_existing_image_destination_is_never_reused(monkeypatch, kind, occupied):
    module = shelf_lab if kind == "package" else capture
    monkeypatch.setattr(module, "uuid", SimpleNamespace(uuid4=lambda: IDENTIFIER))
    identifier = ("pkg_" if kind == "package" else "cap_") + IDENTIFIER.hex
    root = metadata_path(PID).parent
    if kind == "package":
        folder = root / "lab_assets"
        folder.mkdir()
        if occupied in ("image", "both"):
            (folder / f"{identifier}.png").write_bytes(b"Existing photo evidence")
        if occupied in ("metadata", "both"):
            write_json(folder / f"{identifier}.json", {"name": "Existing product"})
    else:
        folder = root / "captures" / identifier
        write_json(folder / "status.json", {"preserved": "Existing capture"})
    before = files(kind, identifier)
    with pytest.raises(AppError) as caught:
        save(kind, "red")
    assert caught.value.status_code == 409
    assert files(kind, identifier) == before
    capture.executor.submit.assert_not_called()


@pytest.mark.parametrize("save_first", [False, True])
def test_computed_capture_and_project_deletion_cannot_leave_orphaned_evidence(monkeypatch, save_first):
    def saving():
        try:
            save("computed")
            return 200
        except AppError as exc:
            return exc.status_code

    def deleting():
        projects.delete_project(PID)

    if save_first:
        saved, _ = overlap(monkeypatch, capture, "_write_status", saving, deleting)
    else:
        _, saved = overlap(monkeypatch, projects, "remove_tree", deleting, saving)
    assert saved == (200 if save_first else 404)
    assert not metadata_path(PID).parent.exists()
